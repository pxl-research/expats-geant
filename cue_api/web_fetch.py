"""Web URL fetching + content extraction for Cue ingestion.

Two public entry points:

- ``fetch_url(url, *, max_bytes)`` — async HTTP fetch with hardening
  (10 s timeout, polite User-Agent, max 5 redirects, size cap, no retries).
- ``route_extractor(result)`` — dispatch by Content-Type: HTML → Trafilatura,
  PDF/Office/text → existing MarkItDown path, else reject.

Plus a small in-process :class:`PreviewCache` keyed by (session_id, url) so
``POST /web/ingest`` can reuse a recent ``POST /web/preview`` without re-fetching.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, urlunparse

import httpx
import trafilatura
from fastapi import HTTPException

from m_shared.utils.url_validation import validate_web_url
from m_shared.vectordb import document_to_markdown

logger = logging.getLogger(__name__)

USER_AGENT = "Cue/0.x (+https://github.com/pxl-research/expat-geant)"
FETCH_TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 5
PREVIEW_CACHE_TTL_SECONDS = 60.0
JS_RENDERED_MIN_BODY = 5_000
JS_RENDERED_MAX_EXTRACTED = 200


HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
TEXT_CONTENT_TYPES = {"text/plain", "text/markdown"}
MARKITDOWN_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class WebFetchError(Exception):
    """Base class for fetch/extract failures."""


class WebFetchTimeout(WebFetchError):
    """Connection or read timed out."""


class WebFetchNetworkError(WebFetchError):
    """DNS, TLS, or other network-layer failure."""


class WebFetchHTTPError(WebFetchError):
    """Origin returned a 4xx/5xx status."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class WebFetchTooLarge(WebFetchError):
    """Response body exceeded the configured byte cap."""


class WebFetchBlocked(WebFetchError):
    """A redirect pointed at an unsafe (internal/private) target — SSRF guard."""


class UnsupportedMediaType(WebFetchError):
    """Content-Type is not one we extract."""


@dataclass
class FetchResult:
    initial_url: str
    final_url: str
    content_type: str
    body: bytes


@dataclass
class ExtractedContent:
    text: str
    title: str | None = None
    extracted_chars: int = 0
    warnings: list[str] = field(default_factory=list)


def normalise_url(url: str) -> str:
    """Normalise for cache keying: lowercase scheme/host, strip fragment, keep query."""
    parsed = urlparse(url.strip())
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def likely_js_rendered_flag(content_type: str, body_len: int, extracted_chars: int) -> bool:
    """Heuristic: HTML response with a substantial body but barely any extracted text."""
    if content_type not in HTML_CONTENT_TYPES:
        return False
    return body_len > JS_RENDERED_MIN_BODY and extracted_chars < JS_RENDERED_MAX_EXTRACTED


async def fetch_url(url: str, *, max_bytes: int) -> FetchResult:
    """Fetch a URL with hardening.

    Raises typed :class:`WebFetchError` subclasses on failure; returns a
    :class:`FetchResult` on success.
    """
    headers = {"User-Agent": USER_AGENT}
    # Redirects are followed manually (follow_redirects=False) so that every hop
    # is re-validated against the SSRF allow-list. httpx's automatic redirects
    # would otherwise bypass the caller's initial validate_web_url() check — an
    # origin could 302 us to http://169.254.169.254/ or an internal host.
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(FETCH_TIMEOUT_SECONDS),
            headers=headers,
            follow_redirects=False,
        ) as client:
            current_url = url
            for _ in range(MAX_REDIRECTS + 1):
                async with client.stream("GET", current_url) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise WebFetchNetworkError("Redirect response had no Location header")
                        current_url = str(resp.url.join(location))
                        try:
                            # validate_web_url does a blocking DNS lookup; keep it
                            # off the event loop.
                            await asyncio.to_thread(validate_web_url, current_url)
                        except HTTPException as exc:
                            raise WebFetchBlocked(f"Unsafe redirect target: {exc.detail}") from exc
                        continue

                    if resp.status_code >= 400:
                        raise WebFetchHTTPError(
                            f"Origin returned HTTP {resp.status_code}",
                            status_code=resp.status_code,
                        )
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise WebFetchTooLarge(
                                f"Response body exceeds maximum allowed size "
                                f"({max_bytes} bytes)"
                            )
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    content_type = (
                        resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    )
                    return FetchResult(
                        initial_url=url,
                        final_url=str(resp.url),
                        content_type=content_type,
                        body=body,
                    )
            raise WebFetchNetworkError(f"Exceeded maximum of {MAX_REDIRECTS} redirects")
    except httpx.TimeoutException as exc:
        raise WebFetchTimeout(f"Fetch timed out after {FETCH_TIMEOUT_SECONDS}s") from exc
    except WebFetchError:
        raise
    except httpx.HTTPError as exc:
        raise WebFetchNetworkError(f"Network error: {exc}") from exc


def extract_html(body: bytes) -> ExtractedContent:
    """Extract clean text + title from an HTML body using Trafilatura."""
    try:
        html = body.decode("utf-8", errors="replace")
    except Exception:
        html = body.decode("latin-1", errors="replace")

    text = trafilatura.extract(
        html,
        favor_precision=True,
        output_format="markdown",
        include_links=False,
        include_images=False,
        # NOTE: deduplicate=False on purpose. Trafilatura's deduplicate flag uses
        # a process-global LRU cache of paragraph fingerprints; after the same
        # URL is extracted a few times in our long-running API process (preview
        # + ingest re-extract + preview again) every paragraph would be filtered
        # as "already seen" and the result becomes empty.
        deduplicate=False,
    )
    text = text or ""

    title: str | None = None
    try:
        metadata = trafilatura.extract_metadata(html)
        if metadata is not None:
            title = getattr(metadata, "title", None)
    except Exception as exc:
        logger.debug("Trafilatura metadata extraction failed: %s", exc)

    return ExtractedContent(text=text, title=title, extracted_chars=len(text))


def _extract_via_markitdown(body: bytes, suffix: str) -> ExtractedContent:
    """Write body to a tempfile and route through the existing MarkItDown wrapper."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(body)
        tmp_path = tmp.name
    try:
        text = document_to_markdown(tmp_path) or ""
        return ExtractedContent(text=text, title=None, extracted_chars=len(text))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def route_extractor(result: FetchResult) -> ExtractedContent:
    """Dispatch to the right extractor based on Content-Type."""
    ct = result.content_type
    if ct in HTML_CONTENT_TYPES:
        extracted = extract_html(result.body)
        if likely_js_rendered_flag(ct, len(result.body), extracted.extracted_chars):
            extracted.warnings.append("likely_js_rendered")
        return extracted
    if ct in MARKITDOWN_CONTENT_TYPES:
        return _extract_via_markitdown(result.body, MARKITDOWN_CONTENT_TYPES[ct])
    if ct in TEXT_CONTENT_TYPES:
        try:
            text = result.body.decode("utf-8", errors="replace")
        except Exception:
            text = result.body.decode("latin-1", errors="replace")
        return ExtractedContent(text=text, title=None, extracted_chars=len(text))
    accepted = sorted(HTML_CONTENT_TYPES | set(MARKITDOWN_CONTENT_TYPES) | TEXT_CONTENT_TYPES)
    raise UnsupportedMediaType(
        f"Unsupported Content-Type {ct!r}. Accepted types: {', '.join(accepted)}."
    )


class PreviewCache:
    """In-process cache for preview→ingest round-trips.

    Keyed by ``(session_id, normalise_url(url))``. Entries expire after
    :data:`PREVIEW_CACHE_TTL_SECONDS`. Not persistent; on miss the caller
    re-fetches.
    """

    def __init__(self, ttl: float = PREVIEW_CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._lock = Lock()
        self._entries: dict[tuple[str, str], tuple[float, FetchResult, ExtractedContent]] = {}

    def _key(self, session_id: str, url: str) -> tuple[str, str]:
        return (session_id, normalise_url(url))

    def put(
        self,
        session_id: str,
        url: str,
        fetch_result: FetchResult,
        extracted: ExtractedContent,
    ) -> None:
        with self._lock:
            self._entries[self._key(session_id, url)] = (
                time.monotonic(),
                fetch_result,
                extracted,
            )

    def get(self, session_id: str, url: str) -> tuple[FetchResult, ExtractedContent] | None:
        key = self._key(session_id, url)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, fetch_result, extracted = entry
            if time.monotonic() - stored_at > self._ttl:
                self._entries.pop(key, None)
                return None
            return fetch_result, extracted

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def map_fetch_error_to_http(exc: WebFetchError) -> tuple[int, str]:
    """Return (status_code, detail) for a typed fetch error."""
    if isinstance(exc, WebFetchTimeout):
        return 504, str(exc)
    if isinstance(exc, WebFetchTooLarge):
        return 413, str(exc)
    if isinstance(exc, UnsupportedMediaType):
        return 415, str(exc)
    if isinstance(exc, WebFetchHTTPError):
        return 502, str(exc)
    if isinstance(exc, WebFetchNetworkError):
        return 502, str(exc)
    return 400, str(exc)


def derive_source_label(url: str, content_type: str, title: str | None) -> str:
    """Derive a human-readable source label for chunk metadata and display.

    HTML → page title (truncated to 100 chars) or hostname+path fallback.
    Non-HTML → URL path basename (e.g. ``regulation_2024_03.pdf``).
    """
    parsed = urlparse(url)
    if content_type in HTML_CONTENT_TYPES:
        if title and title.strip():
            return title.strip()[:100]
        host = parsed.netloc or url
        path = parsed.path or ""
        fallback = f"{host}{path}".rstrip("/")
        return fallback[:100] or url[:100]
    basename = Path(parsed.path).name
    return basename or parsed.netloc or url[:100]
