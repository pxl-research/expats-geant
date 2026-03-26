"""Tests for display-only mode and file-upload session behaviour."""

import httpx
import respx
from fastapi.testclient import TestClient

from cue_ui.main import app

TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}
BASE = "http://localhost:8001"

SURVEY_NO_FORMAT = {
    "id": "survey-lss",
    "title": "LimeSurvey Example",
    "metadata": {},  # no format → capabilities call skipped → display-only
    "sections": [
        {
            "id": "s1",
            "title": "Section 1",
            "questions": [{"id": "q1", "text": "Q1", "type": "open_ended", "answer_options": []}],
        }
    ],
}

SURVEY_WITH_SUBMIT = {
    "id": "survey-ls2",
    "title": "Submittable Survey",
    "metadata": {"format": "lss"},
    "sections": [
        {
            "id": "s1",
            "title": "Section 1",
            "questions": [{"id": "q1", "text": "Q1", "type": "open_ended", "answer_options": []}],
        }
    ],
}


class TestDisplayOnlyMode:
    @respx.mock
    def test_no_submit_button_when_no_capabilities(self):
        """Survey with no format → capabilities skipped → display-only."""
        respx.get(f"{BASE}/surveys/survey-lss").mock(
            return_value=httpx.Response(200, json=SURVEY_NO_FORMAT)
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-lss/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Submit Responses" not in resp.text
        assert "display-only" in resp.text.lower() or "Display-only" in resp.text

    @respx.mock
    def test_no_submit_button_when_capability_absent(self):
        """Adapter has no 'submit' capability → display-only."""
        respx.get(f"{BASE}/surveys/survey-ls2").mock(
            return_value=httpx.Response(200, json=SURVEY_WITH_SUBMIT)
        )
        respx.get(f"{BASE}/adapters/lss/capabilities").mock(
            return_value=httpx.Response(200, json=["read"])  # no "submit"
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-ls2/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Submit Responses" not in resp.text
        assert "display-only" in resp.text.lower() or "Display-only" in resp.text

    @respx.mock
    def test_submit_button_shown_when_submit_in_capabilities(self):
        """Adapter has 'submit' capability → submit button shown."""
        respx.get(f"{BASE}/surveys/survey-ls2").mock(
            return_value=httpx.Response(200, json=SURVEY_WITH_SUBMIT)
        )
        respx.get(f"{BASE}/adapters/lss/capabilities").mock(
            return_value=httpx.Response(200, json=["read", "submit"])
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-ls2/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Submit Responses" in resp.text

    @respx.mock
    def test_display_only_when_capabilities_api_fails(self):
        """If capabilities API fails, fall back to display-only."""
        respx.get(f"{BASE}/surveys/survey-ls2").mock(
            return_value=httpx.Response(200, json=SURVEY_WITH_SUBMIT)
        )
        respx.get(f"{BASE}/adapters/lss/capabilities").mock(
            return_value=httpx.Response(503, json={"detail": "Service down"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/survey-ls2/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Submit Responses" not in resp.text


class TestFileUploadSession:
    @respx.mock
    def test_file_upload_leads_to_document_page(self):
        """After file import, redirect goes to documents page."""
        respx.post(f"{BASE}/surveys/import").mock(
            return_value=httpx.Response(200, json={"survey_id": "imported-xyz"})
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.post(
            "/upload",
            data={"format": "qsf"},
            files={"file": ("s.qsf", b"<qsf/>", "text/xml")},
            cookies=TOKEN_COOKIE,
        )
        assert resp.status_code == 302
        assert "imported-xyz" in resp.headers["location"]

    @respx.mock
    def test_file_upload_survey_is_display_only(self):
        """File-uploaded survey has no format metadata → display-only."""
        respx.get(f"{BASE}/surveys/imported-xyz").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "imported-xyz",
                    "title": "Imported Survey",
                    "metadata": {},  # no format → no capabilities → display-only
                    "sections": [],
                },
            )
        )
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/session/imported-xyz/review", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert "Submit Responses" not in resp.text
