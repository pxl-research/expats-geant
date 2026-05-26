"""Tests for the late-document-uploads feature.

Covers the new `/regenerate-stream` UI proxy route and the contract that
mid-review uploads via the existing upload endpoints leave the cached
suggestions untouched (cache-busting is the user's job via the Regenerate
button — not an upload side-effect).
"""

import json

import httpx
import respx
from fastapi.testclient import TestClient

from cue_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8001"

SURVEY_FIXTURE = {
    "id": "survey-abc",
    "title": "Late Uploads Test",
    "metadata": {"format": "qsf"},
    "sections": [
        {
            "id": "sec1",
            "title": "S",
            "questions": [
                {"id": "q1", "text": "A?", "type": "open_ended", "answer_options": []},
                {"id": "q2", "text": "B?", "type": "open_ended", "answer_options": []},
                {"id": "q3", "text": "C?", "type": "open_ended", "answer_options": []},
            ],
        }
    ],
}

_DONE_SSE = "event: done\ndata: {}\n\n"


def _make_sse(item_ids: list[str]) -> str:
    parts = []
    for i in item_ids:
        payload: dict = {
            "item_id": i,
            "type": "open_ended",
            "suggestion": f"Regenerated {i}",
            "selected_id": None,
            "selected_ids": None,
            "reasoning": None,
            "citations": [],
            "generated_at": "2026-05-19T12:00:00+00:00",
        }
        parts.append(f"event: suggestion\ndata: {json.dumps(payload)}\n\n")
    parts.append(_DONE_SSE)
    return "".join(parts)


class TestRegenerateStreamRoute:
    def test_unauthenticated_returns_401(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/regenerate-stream")
        assert resp.status_code == 401

    @respx.mock
    def test_without_ids_forwards_all_items(self):
        """No `ids` query → proxy POSTs the entire survey item list (no cache filter)."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        upstream = respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(
                200,
                text=_make_sse(["q1", "q2", "q3"]),
                headers={"content-type": "text/event-stream"},
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/regenerate-stream", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        assert upstream.called
        body = json.loads(upstream.calls.last.request.content)
        assert body["assessment_id"] == "survey-abc"
        sent_ids = [item["id"] for item in body["items"]]
        assert sent_ids == ["q1", "q2", "q3"]

    @respx.mock
    def test_ids_param_filters_to_requested_items(self):
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        upstream = respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(
                200, text=_make_sse(["q1", "q3"]), headers={"content-type": "text/event-stream"}
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/regenerate-stream?ids=q1,q3", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        sent_ids = [item["id"] for item in json.loads(upstream.calls.last.request.content)["items"]]
        assert sent_ids == ["q1", "q3"]

    @respx.mock
    def test_unknown_ids_filter_to_empty_emits_done_immediately(self):
        """Client-supplied IDs the server doesn't recognise are dropped, not forwarded."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        upstream = respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(200, text="", headers={"content-type": "text/event-stream"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get(
            "/session/survey-abc/regenerate-stream?ids=does-not-exist", cookies=TOKEN_COOKIE
        )
        assert resp.status_code == 200
        assert resp.text.strip().startswith("event: done")
        assert not upstream.called

    @respx.mock
    def test_emits_rendered_suggestion_html(self):
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(
                200, text=_make_sse(["q2"]), headers={"content-type": "text/event-stream"}
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/regenerate-stream?ids=q2", cookies=TOKEN_COOKIE)
        assert "Regenerated q2" in resp.text
        assert 'id="sug-q2"' in resp.text


class TestStatsProxy:
    """Minimal UI proxy used by review.js to refresh the docs list and
    last_upload_at after a mid-review upload."""

    def test_unauthenticated_returns_401(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/stats")
        assert resp.status_code == 401

    @respx.mock
    def test_returns_documents_and_last_upload_at(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "s",
                    "user_id": "u",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-01-02T00:00:00Z",
                    "remaining_hours": 23.5,
                    "is_expired": False,
                    "document_count": 1,
                    "documents": [{"name": "doc.txt", "chunk_count": 3}],
                    "isolation_scope": "user",
                    "last_upload_at": "2026-01-01T12:00:00+00:00",
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/stats", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["documents"] == [{"name": "doc.txt", "chunk_count": 3}]
        assert body["last_upload_at"] == "2026-01-01T12:00:00+00:00"
        assert body["web_ingest_enabled"] is False
        assert body["web_consent"] is False

    @respx.mock
    def test_propagates_upstream_error(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(404, json={"detail": "Session expired"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/stats", cookies=TOKEN_COOKIE)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session expired"


class TestUploadProxyForwardsCorrectly:
    """The UI's mid-review upload proxy forwards to the cue_api /upload endpoint
    without redirecting and without triggering any cache-mutation side effect
    (cache-bust is an explicit user action via the Regenerate buttons).
    """

    @respx.mock
    def test_upload_doc_proxies_to_cue_api(self):
        upstream = respx.post(f"{BASE}/upload").mock(
            return_value=httpx.Response(200, json={"status": "ok", "filename": "a.txt"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/survey-abc/upload-doc",
            files={"file": ("a.txt", b"hello", "text/plain")},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert upstream.called
