"""Integration tests for cue_ui routes — renders pages with TestClient."""

import httpx
import respx
from fastapi.testclient import TestClient

from cue_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8801"

SURVEY_FIXTURE = {
    "id": "survey-abc",
    "title": "GÉANT Membership Survey",
    "description": "Annual survey",
    "metadata": {"format": "qsf"},
    "sections": [
        {
            "id": "sec1",
            "title": "General",
            "questions": [
                {
                    "id": "q1",
                    "text": "Describe your role",
                    "type": "open_ended",
                    "answer_options": [],
                },
                {
                    "id": "q2",
                    "text": "Organisation type",
                    "type": "single_choice",
                    "answer_options": [
                        {"id": "opt1", "text": "University"},
                        {"id": "opt2", "text": "Research Institute"},
                    ],
                },
            ],
        }
    ],
}

SUGGESTIONS_FIXTURE = {
    "assessment_id": "survey-abc",
    "session_id": "survey-abc",
    "generated_at": "2026-01-01T00:00:00Z",
    "model": "llama",
    "responses": [
        {"item_id": "q1", "type": "open_ended", "suggestion": "Software Engineer", "citations": []},
    ],
}


class TestLandingPage:
    def test_redirect_to_login_when_no_cookie(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["location"]

    def test_landing_redirects_to_sessions(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/", cookies=TOKEN_COOKIE)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/sessions"


class TestAuthCallback:
    def test_callback_sets_cookie_and_redirects(self, monkeypatch):
        """Direct ?token= handoff (dev/manual flow) still works."""
        monkeypatch.setenv("ALLOW_DEV_TOKEN_LOGIN", "1")
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?token=my-jwt")
        assert resp.status_code == 302
        assert "autofill_token" in resp.cookies

    @respx.mock
    def test_callback_oidc_code_proxied_to_autofill(self):
        """OIDC flow: ?code&state proxied server-side to cue-api."""
        respx.get(f"{BASE}/auth/callback").mock(
            return_value=httpx.Response(200, json={"token": "oidc-jwt"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=abc123&state=xyz")
        assert resp.status_code == 302
        assert "autofill_token" in resp.cookies
        assert resp.cookies["autofill_token"] == "oidc-jwt"

    @respx.mock
    def test_callback_oidc_autofill_error_returns_502(self):
        """If cue-api returns an error, surface a 502."""
        respx.get(f"{BASE}/auth/callback").mock(
            return_value=httpx.Response(500, json={"detail": "Keycloak error"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?code=bad&state=bad")
        assert resp.status_code == 502
        assert "Authentication failed" in resp.text

    def test_callback_no_token_returns_400(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback")
        assert resp.status_code == 400
        assert "Authentication failed" in resp.text


class TestUploadRoute:
    @respx.mock
    def test_upload_redirects_to_documents(self):
        respx.post(f"{BASE}/surveys/import").mock(
            return_value=httpx.Response(200, json={"survey_id": "new-survey-1", "warning": None})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload",
            data={"format": "qsf"},
            files={"file": ("survey.qsf", b"<survey/>", "text/xml")},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert "/session/new-survey-1/documents" in resp.headers["location"]

    def test_upload_unsupported_format_shows_error(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload",
            data={"format": "docx"},
            files={"file": ("bad.docx", b"bytes", "application/vnd.openxmlformats")},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 400
        assert "Unsupported format" in resp.text

    def test_upload_redirects_to_login_when_no_cookie(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload",
            data={"format": "qsf"},
            files={"file": ("survey.qsf", b"data", "text/xml")},
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["location"]


class TestSuggestStream:
    def test_suggest_stream_unauthenticated_returns_401(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/suggest-stream")
        assert resp.status_code == 401

    @respx.mock
    def test_suggest_stream_returns_event_stream(self):
        """SSE proxy returns text/event-stream content type."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        sse_body = (
            "event: suggestion\n"
            'data: {"item_id":"q1","type":"open_ended","suggestion":"Software Engineer",'
            '"selected_id":null,"selected_ids":null,"reasoning":null,"citations":[]}\n\n'
            "event: done\ndata: {}\n\n"
        )
        respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(
                200, text=sse_body, headers={"content-type": "text/event-stream"}
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/suggest-stream", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    @respx.mock
    def test_suggest_stream_proxy_emits_suggestion_html(self):
        """Proxy renders suggestion_block.html and emits it as SSE."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        sse_body = (
            "event: suggestion\n"
            'data: {"item_id":"q1","type":"open_ended","suggestion":"Senior Researcher",'
            '"selected_id":null,"selected_ids":null,"reasoning":null,"citations":[]}\n\n'
            "event: done\ndata: {}\n\n"
        )
        respx.post(f"{BASE}/suggest/stream").mock(
            return_value=httpx.Response(
                200, text=sse_body, headers={"content-type": "text/event-stream"}
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/suggest-stream", cookies=TOKEN_COOKIE)
        assert "Senior Researcher" in resp.text
        assert "AI Suggestion" in resp.text

    def test_old_suggest_endpoint_removed(self):
        """GET /session/{id}/suggest no longer exists (returns 404)."""
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/suggest", cookies=TOKEN_COOKIE)
        assert resp.status_code == 404


class TestDeleteSessionByIdProxy:
    """Tests for the cue_ui proxy at DELETE /session/{id}."""

    def test_unauthenticated_returns_401(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/survey-abc")
        assert resp.status_code == 401

    @respx.mock
    def test_swaps_cookie_when_upstream_returns_token(self):
        respx.delete(f"{BASE}/sessions/survey-abc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "survey-abc",
                    "deleted": True,
                    "message": "ok",
                    "token": "new-session-less-token",
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/survey-abc", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "autofill_token=new-session-less-token" in set_cookie

    @respx.mock
    def test_no_cookie_swap_when_no_token(self):
        respx.delete(f"{BASE}/sessions/survey-abc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "survey-abc",
                    "deleted": True,
                    "message": "ok",
                    "token": None,
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/survey-abc", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "autofill_token=" not in resp.headers.get("set-cookie", "")

    @respx.mock
    def test_propagates_upstream_404(self):
        respx.delete(f"{BASE}/sessions/missing").mock(
            return_value=httpx.Response(404, json={"detail": "Session not found"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/missing", cookies=TOKEN_COOKIE)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Session not found"


class TestReviewPage:
    @respx.mock
    def test_render_survey_page(self):
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        respx.get(f"{BASE}/adapters/qsf/capabilities").mock(
            return_value=httpx.Response(200, json=["read", "submit"])
        )
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "",
                    "user_id": "",
                    "created_at": "",
                    "expires_at": "",
                    "remaining_hours": 0,
                    "is_expired": False,
                    "document_count": 0,
                    "documents": [],
                    "isolation_scope": "session",
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "GÉANT Membership Survey" in resp.text

    @respx.mock
    def test_expired_session_shows_expiry_page(self):
        respx.get(f"{BASE}/surveys/expired-id").mock(
            return_value=httpx.Response(410, json={"detail": "Session expired"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/expired-id/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 410
        assert "expired" in resp.text.lower()


class TestUploadFromApiRoute:
    @respx.mock
    def test_upload_from_api_success_redirects_to_documents(self):
        """Successful API import redirects to /session/{id}/documents."""
        respx.post(f"{BASE}/surveys/import-from-api").mock(
            return_value=httpx.Response(200, json={"survey_id": "api-session-1", "warning": None})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload-from-api",
            data={
                "format": "lss",
                "survey_id": "123",
                "api_url": "https://ls.example.com/rpc",
                "username": "admin",
                "password": "pw",
                "api_token": "",
                "datacenter_id": "",
            },
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert "/session/api-session-1/documents" in resp.headers["location"]

    @respx.mock
    def test_upload_from_api_error_rerenders_upload_no_password(self):
        """API error re-renders upload page with error and form values (no password)."""
        respx.post(f"{BASE}/surveys/import-from-api").mock(
            return_value=httpx.Response(400, json={"detail": "LimeSurvey API URL must be set"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload-from-api",
            data={
                "format": "lss",
                "survey_id": "123",
                "api_url": "",
                "username": "admin",
                "password": "secret",
                "api_token": "",
                "datacenter_id": "",
            },
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 400
        assert "LimeSurvey API URL must be set" in resp.text
        # Survey ID should be preserved
        assert "123" in resp.text
        # Password must NOT appear in the rendered HTML
        assert "secret" not in resp.text

    @respx.mock
    def test_upload_from_api_qsf_error_rerenders_upload_no_token(self):
        """API error for QSF re-renders upload page without echoing the API token."""
        respx.post(f"{BASE}/surveys/import-from-api").mock(
            return_value=httpx.Response(400, json={"detail": "Qualtrics API token must be set"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload-from-api",
            data={
                "format": "qsf",
                "survey_id": "SV_123",
                "api_url": "",
                "username": "",
                "password": "",
                "api_token": "secret-token",
                "datacenter_id": "ca1",
            },
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 400
        assert "Qualtrics API token must be set" in resp.text
        # Survey ID should be preserved
        assert "SV_123" in resp.text
        # API token must NOT appear in the rendered HTML
        assert "secret-token" not in resp.text

    def test_upload_from_api_unauthenticated_redirects_to_login(self):
        """No auth cookie → redirect to /auth/login."""
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload-from-api",
            data={
                "format": "lss",
                "survey_id": "123",
                "api_url": "",
                "username": "",
                "password": "",
                "api_token": "",
                "datacenter_id": "",
            },
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["location"]


class TestSubmitRoute:
    @respx.mock
    def test_submit_success_shows_confirmation(self):
        respx.post(f"{BASE}/sessions/survey-abc/submit").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/survey-abc/submit",
            data={"q_q1": "My answer"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert "Submitted" in resp.text

    @respx.mock
    def test_submit_shows_cleanup_modal(self):
        respx.post(f"{BASE}/sessions/survey-abc/submit").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/survey-abc/submit",
            data={"q_q1": "My answer"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert "cleanup-modal" in resp.text
        assert "Delete session data" in resp.text

    @respx.mock
    def test_submit_error_preserves_answers(self):
        respx.post(f"{BASE}/sessions/survey-abc/submit").mock(
            return_value=httpx.Response(503, json={"detail": "Platform down"})
        )
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/survey-abc/submit",
            data={"q_q1": "My answer"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 503
        assert "Platform down" in resp.text


class TestReviewStateProxy:
    @respx.mock
    def test_put_review_state_proxies_to_api(self):
        respx.put(f"{BASE}/review-state/q1").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = TestClient(app)
        resp = client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "yes"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @respx.mock
    def test_get_review_state_proxies_to_api(self):
        respx.get(f"{BASE}/review-state").mock(
            return_value=httpx.Response(
                200, json={"states": {"q1": {"state": "accepted", "value": "yes"}}}
            )
        )
        client = TestClient(app)
        resp = client.get("/review-state", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "q1" in resp.json()["states"]

    def test_put_review_state_unauthenticated(self):
        client = TestClient(app)
        resp = client.put("/review-state/q1", json={"state": "accepted"})
        assert resp.status_code == 401

    def test_get_review_state_unauthenticated(self):
        client = TestClient(app)
        resp = client.get("/review-state")
        assert resp.status_code == 401


class TestReviewPageWithCachedSuggestions:
    @respx.mock
    def test_cached_suggestions_rendered_inline(self):
        """When cached suggestions exist, template renders suggestion blocks instead of spinners."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        respx.get(f"{BASE}/adapters/qsf/capabilities").mock(
            return_value=httpx.Response(200, json=["read"])
        )
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "",
                    "user_id": "",
                    "created_at": "",
                    "expires_at": "",
                    "remaining_hours": 0,
                    "is_expired": False,
                    "document_count": 0,
                    "documents": [],
                    "isolation_scope": "session",
                },
            )
        )
        respx.get(f"{BASE}/review-state").mock(
            return_value=httpx.Response(200, json={"states": {}})
        )
        respx.get(f"{BASE}/cached-suggestions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "suggestions": {
                        "q1": {
                            "item_id": "q1",
                            "type": "open_ended",
                            "suggestion": "Software Engineer",
                            "reasoning": "Based on your profile",
                            "selected_id": None,
                            "selected_ids": None,
                            "citations": [],
                        }
                    }
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "AI Suggestion" in resp.text
        assert "Software Engineer" in resp.text

    @respx.mock
    def test_no_cache_shows_spinners(self):
        """When no cached suggestions, template renders spinners for SSE."""
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        respx.get(f"{BASE}/adapters/qsf/capabilities").mock(
            return_value=httpx.Response(200, json=["read"])
        )
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "",
                    "user_id": "",
                    "created_at": "",
                    "expires_at": "",
                    "remaining_hours": 0,
                    "is_expired": False,
                    "document_count": 0,
                    "documents": [],
                    "isolation_scope": "session",
                },
            )
        )
        respx.get(f"{BASE}/review-state").mock(
            return_value=httpx.Response(200, json={"states": {}})
        )
        respx.get(f"{BASE}/cached-suggestions").mock(
            return_value=httpx.Response(200, json={"suggestions": {}})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-abc/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Generating suggestion" in resp.text
        assert "sse-connect" in resp.text


class TestWebProxyRoutes:
    @respx.mock
    def test_preview_proxy_forwards_payload_and_propagates_body(self):
        respx.post(f"{BASE}/web/preview").mock(
            return_value=httpx.Response(
                200,
                json={
                    "initial_url": "https://example.com/a",
                    "final_url": "https://example.com/a",
                    "hostname": "example.com",
                    "title": "Hello",
                    "content_type": "text/html",
                    "extracted_chars": 120,
                    "preview_text": "Hello world",
                    "warnings": [],
                    "already_ingested_at": None,
                    "source_label": "Hello",
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/sess_a/web/preview",
            json={"url": "https://example.com/a"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["final_url"] == "https://example.com/a"
        assert body["title"] == "Hello"

    @respx.mock
    def test_preview_proxy_propagates_415(self):
        respx.post(f"{BASE}/web/preview").mock(
            return_value=httpx.Response(415, json={"detail": "Unsupported"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/sess_a/web/preview",
            json={"url": "https://example.com/x.png"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 415
        assert resp.json()["detail"] == "Unsupported"

    @respx.mock
    def test_ingest_proxy_forwards_and_returns_ok(self):
        respx.post(f"{BASE}/web/ingest").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "success",
                    "source": "hello",
                    "source_url": "https://example.com/a",
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/sess_a/web/ingest",
            json={"url": "https://example.com/a"},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    @respx.mock
    def test_consent_proxy_forwards_toggle(self):
        respx.put(f"{BASE}/session/web-consent").mock(
            return_value=httpx.Response(200, json={"web_consent": True})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.put(
            "/session/sess_a/web-consent",
            json={"enabled": True},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 200
        assert resp.json() == {"web_consent": True}

    def test_preview_proxy_requires_url(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/sess_a/web/preview",
            json={"url": ""},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 400

    def test_preview_proxy_requires_auth(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/session/sess_a/web/preview",
            json={"url": "https://example.com/a"},
        )
        assert resp.status_code == 401


class TestSessionStatsProxyWebFields:
    @respx.mock
    def test_stats_proxy_propagates_web_flags(self):
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "sess_a",
                    "user_id": "user_a",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-01-02T00:00:00Z",
                    "remaining_hours": 24.0,
                    "is_expired": False,
                    "document_count": 0,
                    "documents": [],
                    "isolation_scope": "user",
                    "last_upload_at": None,
                    "web_ingest_enabled": True,
                    "web_consent": True,
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/sess_a/stats", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["web_ingest_enabled"] is True
        assert body["web_consent"] is True


class TestRemoveDocumentProxy:
    @respx.mock
    def test_proxy_forwards_and_returns_ok(self):
        respx.delete(f"{BASE}/session/documents/notes-txt").mock(
            return_value=httpx.Response(200, json={"status": "ok", "name": "notes-txt"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/sess_a/documents/notes-txt", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "name": "notes-txt"}

    @respx.mock
    def test_proxy_propagates_404(self):
        respx.delete(f"{BASE}/session/documents/missing").mock(
            return_value=httpx.Response(404, json={"detail": "Source 'missing' not found"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/sess_a/documents/missing", cookies=TOKEN_COOKIE)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_proxy_requires_auth(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.delete("/session/sess_a/documents/anything")
        assert resp.status_code == 401
