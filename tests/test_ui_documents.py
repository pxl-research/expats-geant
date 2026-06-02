"""Tests for the GET documents page (four-card layout + per-card fetch ingest)."""

import httpx
import respx
from fastapi.testclient import TestClient

from cue_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8801"
SESSION_ID = "session-doc-test"


def _stats_response(documents=None, web_ingest_enabled=False, web_consent=False):
    return {
        "session_id": SESSION_ID,
        "user_id": "user-test",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-01-02T00:00:00Z",
        "remaining_hours": 24.0,
        "is_expired": False,
        "document_count": len(documents or []),
        "documents": documents or [],
        "isolation_scope": "user",
        "last_upload_at": None,
        "web_ingest_enabled": web_ingest_enabled,
        "web_consent": web_consent,
    }


class TestDocumentsPageLayout:
    @respx.mock
    def test_renders_four_cards_when_web_enabled(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(200, json=_stats_response(web_ingest_enabled=True))
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        body = resp.text
        assert "Files" in body
        assert "Paste Text" in body
        assert "Add a Web Source" in body
        assert "Your Sources" in body
        assert f"/session/{SESSION_ID}/review" in body
        assert 'id="continue-btn"' in body

    @respx.mock
    def test_renders_three_cards_when_web_disabled(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(200, json=_stats_response(web_ingest_enabled=False))
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        body = resp.text
        assert "Files" in body
        assert "Paste Text" in body
        assert "Add a Web Source" not in body
        assert "Your Sources" in body

    @respx.mock
    def test_empty_sources_shows_empty_state(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(200, json=_stats_response(documents=[]))
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "No sources yet" in resp.text

    @respx.mock
    def test_existing_sources_listed(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json=_stats_response(
                    documents=[
                        {"name": "cv.pdf", "chunk_count": 4},
                        {"name": "notes", "chunk_count": 1},
                    ]
                ),
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        body = resp.text
        assert "cv.pdf" in body
        assert "4 chunks" in body
        assert "notes" in body
        assert "1 chunk</td>" in body or "1 chunk\n" in body or ">1 chunk" in body
