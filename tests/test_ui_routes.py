"""Integration tests for m_ui routes — renders pages with TestClient."""

import httpx
import respx
from fastapi.testclient import TestClient

from m_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8001"

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

    def test_render_landing_when_authenticated(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Upload" in resp.text


class TestAuthCallback:
    def test_callback_sets_cookie_and_redirects(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback?token=my-jwt")
        assert resp.status_code == 302
        assert "autofill_token" in resp.cookies

    def test_callback_no_token_returns_400(self):
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/auth/callback")
        assert resp.status_code == 400
        assert "Authentication failed" in resp.text


class TestUploadRoute:
    @respx.mock
    def test_upload_redirects_to_documents(self):
        respx.post(f"{BASE}/surveys/import").mock(
            return_value=httpx.Response(200, json={"survey_id": "new-survey-1"})
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


class TestReviewPage:
    @respx.mock
    def test_render_survey_page(self):
        respx.get(f"{BASE}/surveys/survey-abc").mock(
            return_value=httpx.Response(200, json=SURVEY_FIXTURE)
        )
        respx.get(f"{BASE}/adapters/qsf/capabilities").mock(
            return_value=httpx.Response(200, json=["read", "submit"])
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
