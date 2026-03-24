"""Tests for document upload step — success, format errors, API errors, skip."""

import httpx
import respx
from fastapi.testclient import TestClient

from cue_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8001"
SESSION_ID = "session-doc-test"


class TestDocumentUploadSuccess:
    @respx.mock
    def test_all_files_uploaded_redirects_to_review(self):
        respx.post(f"{BASE}/upload").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            files=[
                ("files", ("doc1.pdf", b"pdf1", "application/pdf")),
                ("files", ("doc2.txt", b"txt1", "text/plain")),
            ],
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert f"/session/{SESSION_ID}/review" in resp.headers["location"]

    @respx.mock
    def test_single_file_success_redirects(self):
        """Single file upload succeeds → redirect to review."""
        respx.post(f"{BASE}/upload").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            files=[("files", ("report.pdf", b"pdf content", "application/pdf"))],
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert f"/session/{SESSION_ID}/review" in resp.headers["location"]


class TestDocumentUploadErrors:
    @respx.mock
    def test_unsupported_format_shows_per_file_error(self):
        respx.post(f"{BASE}/upload").mock(
            return_value=httpx.Response(400, json={"detail": "Unsupported file type: exe"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            files=[("files", ("bad.exe", b"exe", "application/octet-stream"))],
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 422
        assert "bad.exe" in resp.text
        assert "Unsupported file type" in resp.text

    @respx.mock
    def test_api_error_shows_inline_error_retry_available(self):
        respx.post(f"{BASE}/upload").mock(
            return_value=httpx.Response(500, json={"detail": "Ingestion pipeline error"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            files=[("files", ("report.pdf", b"pdf", "application/pdf"))],
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 422
        assert "report.pdf" in resp.text
        # The page should still show the upload form (retry available)
        assert "Upload" in resp.text or "documents" in resp.text.lower()

    @respx.mock
    def test_partial_failure_shows_only_failed_files(self):
        """One file succeeds, one fails — only the failed file shows an error."""
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"status": "success"})
            return httpx.Response(400, json={"detail": "Unsupported type"})

        respx.post(f"{BASE}/upload").mock(side_effect=side_effect)
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            files=[
                ("files", ("good.pdf", b"pdf", "application/pdf")),
                ("files", ("bad.exe", b"exe", "application/octet-stream")),
            ],
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 422
        assert "bad.exe" in resp.text
        # good.pdf should not appear in errors
        assert "good.pdf" not in resp.text


class TestDocumentUploadSkip:
    def test_skip_link_points_to_review(self):
        """Skip link on documents page goes directly to review (no upload form submit)."""
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        # The skip link URL should point to the review page
        assert f"/session/{SESSION_ID}/review" in resp.text
        assert "Skip" in resp.text

    def test_skip_link_present_on_documents_page(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert f"/session/{SESSION_ID}/review" in resp.text

    def test_post_with_no_files_redirects_to_review(self):
        """Submitting the document form with no files selected redirects to review."""
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            f"/session/{SESSION_ID}/documents",
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == f"/session/{SESSION_ID}/review"
