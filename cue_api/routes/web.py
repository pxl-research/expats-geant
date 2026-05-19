"""Cue API: web URL preview + ingest routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, status

from cue_api.ingest import find_source_url_ingest_time, ingest_extracted_text_into_store
from cue_api.models import (
    WebIngestResponse,
    WebPreviewRequest,
    WebPreviewResponse,
)
from cue_api.web_fetch import (
    PreviewCache,
    WebFetchError,
    derive_source_label,
    fetch_url,
    map_fetch_error_to_http,
    route_extractor,
)
from m_shared.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()
_preview_cache = PreviewCache()


def _gate_check(request: Request) -> None:
    """Raise 403 unless both the operator flag and per-session consent are on."""
    if not getattr(request.app.state, "web_ingest_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web ingestion is not enabled for this deployment",
        )
    session = request.state.session
    if not (session and session.metadata.get("web_consent")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web sources are not enabled for this session. "
            "Grant consent via PUT /session/web-consent first.",
        )


async def _fetch_and_extract(request: Request, url: str):
    """Perform fetch + route_extractor, mapping typed errors to HTTPException."""
    max_bytes = request.app.state.max_file_size_mb * 1024 * 1024
    try:
        fetch_result = await fetch_url(url, max_bytes=max_bytes)
        extracted = route_extractor(fetch_result)
    except WebFetchError as exc:
        code, detail = map_fetch_error_to_http(exc)
        raise HTTPException(status_code=code, detail=detail) from exc
    return fetch_result, extracted


@router.post("/web/preview", response_model=WebPreviewResponse)
@limiter.limit("10/minute")
async def preview_web_url(request: Request, body: WebPreviewRequest):
    """Fetch a URL and return a preview without storing chunks."""
    _gate_check(request)
    session = request.state.session
    claims = request.state.claims
    audit_logger = request.app.state.audit_logger
    manager = request.state.session_manager

    fetch_result, extracted = await _fetch_and_extract(request, body.url)

    source_label = derive_source_label(body.url, fetch_result.content_type, extracted.title)

    already_ingested_at: str | None = None
    try:
        store = manager.get_vector_store(session.session_id)
        prior_ts = find_source_url_ingest_time(store, fetch_result.final_url)
        if prior_ts is not None:
            already_ingested_at = datetime.fromtimestamp(prior_ts, tz=UTC).isoformat()
    except FileNotFoundError:
        pass

    _preview_cache.put(session.session_id, body.url, fetch_result, extracted)

    likely_js = "likely_js_rendered" in extracted.warnings
    if audit_logger:
        audit_logger.log_web_fetch(
            session_id=session.session_id,
            url=body.url,
            final_url=fetch_result.final_url,
            content_type=fetch_result.content_type,
            extracted_chars=extracted.extracted_chars,
            likely_js_rendered=likely_js,
            ingested=False,
            user_id=claims.get("user_id"),
        )

    return WebPreviewResponse(
        initial_url=body.url,
        final_url=fetch_result.final_url,
        hostname=urlparse(fetch_result.final_url).netloc,
        title=extracted.title,
        content_type=fetch_result.content_type,
        extracted_chars=extracted.extracted_chars,
        preview_text=extracted.text[:500],
        warnings=extracted.warnings,
        already_ingested_at=already_ingested_at,
        source_label=source_label,
    )


@router.post("/web/ingest", response_model=WebIngestResponse)
@limiter.limit("10/minute")
async def ingest_web_url(request: Request, body: WebPreviewRequest):
    """Ingest a previously-previewed URL (re-fetches on cache miss)."""
    _gate_check(request)
    session = request.state.session
    claims = request.state.claims
    audit_logger = request.app.state.audit_logger
    manager = request.state.session_manager

    cached = _preview_cache.get(session.session_id, body.url)
    if cached is None:
        fetch_result, extracted = await _fetch_and_extract(request, body.url)
    else:
        fetch_result, extracted = cached

    if not extracted.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extracted content is empty; nothing to ingest.",
        )

    source_label = derive_source_label(body.url, fetch_result.content_type, extracted.title)

    try:
        store = manager.get_vector_store(session.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
        ) from exc

    collection_name = await asyncio.to_thread(
        ingest_extracted_text_into_store,
        text=extracted.text,
        source_label=source_label,
        source_url=fetch_result.final_url,
        store=store,
    )

    likely_js = "likely_js_rendered" in extracted.warnings
    if audit_logger:
        audit_logger.log_web_fetch(
            session_id=session.session_id,
            url=body.url,
            final_url=fetch_result.final_url,
            content_type=fetch_result.content_type,
            extracted_chars=extracted.extracted_chars,
            likely_js_rendered=likely_js,
            ingested=True,
            user_id=claims.get("user_id"),
        )

    return WebIngestResponse(
        status="success",
        source=collection_name,
        source_url=fetch_result.final_url,
    )
