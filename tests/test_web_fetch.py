"""Unit tests for cue_api/web_fetch.py."""

from __future__ import annotations

import time
from unittest.mock import patch

import httpx
import pytest
import respx

from cue_api.web_fetch import (
    PREVIEW_CACHE_TTL_SECONDS,
    ExtractedContent,
    FetchResult,
    PreviewCache,
    UnsupportedMediaType,
    WebFetchHTTPError,
    WebFetchTimeout,
    WebFetchTooLarge,
    derive_source_label,
    extract_html,
    fetch_url,
    likely_js_rendered_flag,
    normalise_url,
    route_extractor,
)


class TestNormaliseUrl:
    def test_lowercase_scheme_and_host(self):
        assert normalise_url("HTTPS://Example.COM/Page?q=1") == "https://example.com/Page?q=1"

    def test_strip_fragment(self):
        assert normalise_url("https://example.com/page#section") == "https://example.com/page"

    def test_keep_query(self):
        assert (
            normalise_url("https://example.com/?utm=foo&page=2")
            == "https://example.com/?utm=foo&page=2"
        )


class TestLikelyJsRenderedFlag:
    def test_sparse_html_flagged(self):
        assert likely_js_rendered_flag("text/html", body_len=10_000, extracted_chars=50)

    def test_html_with_substantial_text_not_flagged(self):
        assert not likely_js_rendered_flag("text/html", body_len=10_000, extracted_chars=2000)

    def test_small_html_not_flagged(self):
        assert not likely_js_rendered_flag("text/html", body_len=1000, extracted_chars=10)

    def test_pdf_never_flagged(self):
        assert not likely_js_rendered_flag("application/pdf", body_len=100_000, extracted_chars=50)


class TestFetchUrl:
    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_path_html(self):
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(
                200,
                content=b"<html><body><p>Hello</p></body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
            )
        )
        result = await fetch_url("https://example.com/page", max_bytes=1_000_000)
        assert result.initial_url == "https://example.com/page"
        assert result.final_url == "https://example.com/page"
        assert result.content_type == "text/html"
        assert b"<p>Hello</p>" in result.body

    @pytest.mark.asyncio
    @respx.mock
    async def test_redirect_records_final_url(self):
        respx.get("https://example.com/old").mock(
            return_value=httpx.Response(302, headers={"location": "https://example.com/new"})
        )
        respx.get("https://example.com/new").mock(
            return_value=httpx.Response(200, content=b"ok", headers={"content-type": "text/plain"})
        )
        result = await fetch_url("https://example.com/old", max_bytes=1_000_000)
        assert result.initial_url == "https://example.com/old"
        assert result.final_url == "https://example.com/new"

    @pytest.mark.asyncio
    @respx.mock
    async def test_oversize_rejected(self):
        big_body = b"x" * 2000
        respx.get("https://example.com/big").mock(
            return_value=httpx.Response(
                200, content=big_body, headers={"content-type": "text/plain"}
            )
        )
        with pytest.raises(WebFetchTooLarge):
            await fetch_url("https://example.com/big", max_bytes=500)

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_raises(self):
        respx.get("https://example.com/404").mock(
            return_value=httpx.Response(404, content=b"not found")
        )
        with pytest.raises(WebFetchHTTPError) as exc_info:
            await fetch_url("https://example.com/404", max_bytes=1_000_000)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_raises(self):
        respx.get("https://example.com/slow").mock(side_effect=httpx.ReadTimeout("slow"))
        with pytest.raises(WebFetchTimeout):
            await fetch_url("https://example.com/slow", max_bytes=1_000_000)


class TestRouteExtractor:
    def test_html_uses_trafilatura(self):
        html = b"""
        <html><head><title>My Article</title></head>
        <body><article><p>This is the main content of the article that should be extracted.</p>
        <p>A second paragraph adds more body so the extractor has something to work with.</p>
        </article></body></html>
        """
        result = route_extractor(
            FetchResult(
                initial_url="https://example.com/a",
                final_url="https://example.com/a",
                content_type="text/html",
                body=html,
            )
        )
        assert "main content" in result.text.lower()
        assert result.title == "My Article"

    def test_plain_text_pass_through(self):
        result = route_extractor(
            FetchResult(
                initial_url="https://example.com/t",
                final_url="https://example.com/t",
                content_type="text/plain",
                body=b"hello world",
            )
        )
        assert "hello world" in result.text

    def test_unsupported_raises(self):
        with pytest.raises(UnsupportedMediaType):
            route_extractor(
                FetchResult(
                    initial_url="https://example.com/i",
                    final_url="https://example.com/i",
                    content_type="image/png",
                    body=b"\x89PNG",
                )
            )

    def test_sparse_html_gets_js_rendered_warning(self):
        sparse_html = b"<html><body>" + b"x" * 10_000 + b"</body></html>"
        with patch("cue_api.web_fetch.trafilatura.extract", return_value="tiny"):
            with patch("cue_api.web_fetch.trafilatura.extract_metadata", return_value=None):
                result = route_extractor(
                    FetchResult(
                        initial_url="https://example.com/spa",
                        final_url="https://example.com/spa",
                        content_type="text/html",
                        body=sparse_html,
                    )
                )
        assert "likely_js_rendered" in result.warnings


class TestExtractHtml:
    def test_handles_bytes_decoding(self):
        html = b"<html><body><article><p>Some content here for the extractor.</p></article></body></html>"
        result = extract_html(html)
        assert isinstance(result, ExtractedContent)
        assert result.extracted_chars == len(result.text)


class TestPreviewCache:
    def test_round_trip(self):
        cache = PreviewCache()
        fr = FetchResult(initial_url="u", final_url="u", content_type="text/html", body=b"")
        ec = ExtractedContent(text="hi", title="t", extracted_chars=2)
        cache.put("sess1", "https://example.com/a", fr, ec)
        got = cache.get("sess1", "https://example.com/a")
        assert got is not None
        assert got[1].text == "hi"

    def test_session_isolation(self):
        cache = PreviewCache()
        fr = FetchResult(initial_url="u", final_url="u", content_type="text/html", body=b"")
        ec = ExtractedContent(text="hi", title=None, extracted_chars=2)
        cache.put("sess1", "https://example.com/a", fr, ec)
        assert cache.get("sess2", "https://example.com/a") is None

    def test_url_normalisation_for_lookup(self):
        cache = PreviewCache()
        fr = FetchResult(initial_url="u", final_url="u", content_type="text/html", body=b"")
        ec = ExtractedContent(text="hi", title=None, extracted_chars=2)
        cache.put("sess1", "https://Example.com/a#frag", fr, ec)
        assert cache.get("sess1", "https://example.com/a") is not None

    def test_ttl_expiry(self):
        cache = PreviewCache(ttl=0.0)
        fr = FetchResult(initial_url="u", final_url="u", content_type="text/html", body=b"")
        ec = ExtractedContent(text="hi", title=None, extracted_chars=2)
        cache.put("sess1", "https://example.com/a", fr, ec)
        time.sleep(0.01)
        assert cache.get("sess1", "https://example.com/a") is None

    def test_module_default_ttl(self):
        assert PREVIEW_CACHE_TTL_SECONDS == 60.0


class TestDeriveSourceLabel:
    def test_html_with_title(self):
        assert (
            derive_source_label("https://example.com/a", "text/html", "My Awesome Article")
            == "My Awesome Article"
        )

    def test_html_without_title_falls_back_to_host_path(self):
        label = derive_source_label("https://example.com/path/page", "text/html", None)
        assert "example.com" in label

    def test_pdf_uses_basename(self):
        assert (
            derive_source_label("https://example.com/docs/regulation.pdf", "application/pdf", None)
            == "regulation.pdf"
        )

    def test_truncates_long_title(self):
        long_title = "a" * 200
        assert len(derive_source_label("https://example.com/", "text/html", long_title)) == 100
