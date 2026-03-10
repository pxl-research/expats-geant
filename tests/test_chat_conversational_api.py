"""Integration tests for the conversational session API (Section 4 of implement-chat-api).

Covers:
- POST/GET /chat/sessions — session lifecycle
- GET/DELETE /chat/{session_id} — session metadata and deletion
- POST /chat/{session_id}/reset — clear draft and vocab only
- POST /chat/{session_id} — chat turn (plain text + survey update)
- GET /chat/{session_id}/survey — current draft survey
- GET/PUT /chat/{session_id}/style — style profile management
- POST /chat/{session_id}/style/upload — style document upload
- POST /chat/{session_id}/upload — content document upload
- Integration scenarios: scratch-to-export, session isolation, session resume
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from m_chat.api import create_app
from m_chat.session import (
    DEFAULT_STYLE_PROFILE,
    save_draft_survey,
    save_tag_vocabulary,
)
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.models.survey import Survey
from m_shared.session.manager import SessionManager

# ---------------------------------------------------------------------------
# Reused sample payloads (mirrors test_chat_api.py)
# ---------------------------------------------------------------------------

MINIMAL_LSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>42</sid>
    <surveyls_title>Test Survey</surveyls_title>
    <surveyls_description>Test description</surveyls_description>
  </row></rows></surveys>
  <groups><rows>
    <row>
      <gid>1</gid><group_name>Section One</group_name>
      <description></description><group_order>1</group_order>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>10</qid><gid>1</gid><type>T</type>
      <question>What is your name?</question><mandatory>N</mandatory>
      <question_order>1</question_order><parent_qid>0</parent_qid>
    </row>
  </rows></questions>
  <answers><rows/></answers>
</document>
"""

SAMPLE_SURVEY_DICT = {
    "id": "survey1",
    "title": "Test Survey",
    "description": "A test survey",
    "sections": [
        {
            "id": "sec1",
            "title": "Section 1",
            "description": "",
            "questions": [
                {
                    "id": "q1",
                    "text": "How are you?",
                    "type": "open_ended",
                    "order": 0,
                    "answer_options": [],
                    "required": False,
                    "min_value": None,
                    "max_value": None,
                    "step": None,
                    "metadata": {},
                }
            ],
            "order": 0,
            "metadata": {},
        }
    ],
    "metadata": {},
}

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret"


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def app(session_manager, jwt_secret):
    application = create_app(session_manager=session_manager)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.create_completion.return_value = "How can I help you design your survey?"
    return llm


@pytest.fixture
def app_with_llm(session_manager, jwt_secret, mock_llm):
    application = create_app(session_manager=session_manager, llm_client=mock_llm)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_llm(app_with_llm):
    return TestClient(app_with_llm, raise_server_exceptions=False)


def _make_auth_headers(user_id: str = "test_user") -> dict:
    """Build Authorization headers for the given user_id (JWT_SECRET must be set)."""
    token = create_token(
        user_id=user_id,
        session_id="auth_session",
        org="test_org",
        roles=["user"],
    )
    return {"Authorization": f"Bearer {token}"}


def _create_chat_session(client, headers: dict) -> str:
    """Helper: POST /chat/sessions and return the new session_id."""
    resp = client.post("/chat/sessions", json={}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# TestSessionLifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    def test_create_session_returns_201_with_session_id(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        resp = client.post("/chat/sessions", json={}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["user_id"] == "user1"
        assert "created_at" in data
        assert "expires_at" in data
        assert "style_profile" in data

    def test_list_sessions_returns_created_session(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get("/chat/sessions", headers=headers)
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        session_ids = [s["session_id"] for s in sessions]
        assert sid in session_ids

    def test_get_session_metadata(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["user_id"] == "user1"
        assert "style_profile" in data

    def test_get_foreign_session_returns_403(self, client, jwt_secret):
        headers1 = _make_auth_headers("user1")
        headers2 = _make_auth_headers("user2")
        sid = _create_chat_session(client, headers1)
        resp = client.get(f"/chat/{sid}", headers=headers2)
        assert resp.status_code == 403

    def test_delete_session_returns_200(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.delete(f"/chat/{sid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["session_id"] == sid
        # session should now be gone
        resp2 = client.get(f"/chat/{sid}", headers=headers)
        assert resp2.status_code == 403

    def test_reset_session_clears_draft_and_vocab_only(self, client, jwt_secret, session_manager):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        base_path = str(session_manager.base_path)

        # Manually write draft and vocab
        survey = Survey(**SAMPLE_SURVEY_DICT)
        save_draft_survey(base_path, sid, survey)
        save_tag_vocabulary(base_path, sid, {"demographics": ["q1"]})

        resp = client.post(f"/chat/{sid}/reset", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reset"] is True
        assert "draft_survey.json" in data["cleared"]
        assert "tag_vocabulary.json" in data["cleared"]

        # Confirm draft is gone
        resp2 = client.get(f"/chat/{sid}/survey", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["survey"] is None

        # Confirm session itself still exists
        resp3 = client.get(f"/chat/{sid}", headers=headers)
        assert resp3.status_code == 200


# ---------------------------------------------------------------------------
# TestChatTurnEndpoint
# ---------------------------------------------------------------------------


class TestChatTurnEndpoint:
    def test_chat_turn_plain_text_response(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        mock_llm.create_completion.return_value = "Sure, I can help with that."

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Help me design a student survey."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Sure, I can help with that."
        assert data["survey_updated"] is False

    def test_chat_turn_survey_update_parsed(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        survey_json = json.dumps(SAMPLE_SURVEY_DICT)
        mock_llm.create_completion.return_value = (
            f"Here is the updated survey.<survey_update>{survey_json}</survey_update>"
        )

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create a basic survey."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["survey_updated"] is True
        assert "Here is the updated survey." in data["message"]

    def test_chat_turn_no_llm_returns_500(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.post(
            f"/chat/{sid}",
            json={"message": "Hello"},
            headers=headers,
        )
        assert resp.status_code == 500

    def test_get_survey_after_update(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        survey_json = json.dumps(SAMPLE_SURVEY_DICT)
        mock_llm.create_completion.return_value = (
            f"Updated!<survey_update>{survey_json}</survey_update>"
        )
        client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create a survey."},
            headers=headers,
        )

        resp = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert resp.status_code == 200
        survey = resp.json()["survey"]
        assert survey is not None
        assert survey["title"] == "Test Survey"

    def test_get_survey_no_draft_returns_null(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}/survey", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["survey"] is None


# ---------------------------------------------------------------------------
# TestStyleEndpoints
# ---------------------------------------------------------------------------


class TestStyleEndpoints:
    def test_get_style_returns_defaults(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}/style", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["style_profile"]["language"] == DEFAULT_STYLE_PROFILE["language"]

    def test_put_style_updates_language(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.put(
            f"/chat/{sid}/style",
            json={"language": "nl"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["style_profile"]["language"] == "nl"

    def test_put_style_partial_update_preserves_other_fields(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        # First set language
        client.put(f"/chat/{sid}/style", json={"language": "fr"}, headers=headers)
        # Then set free_text only
        resp = client.put(
            f"/chat/{sid}/style",
            json={"free_text": "Use formal tone."},
            headers=headers,
        )
        assert resp.status_code == 200
        profile = resp.json()["style_profile"]
        assert profile["language"] == "fr"
        assert profile["free_text"] == "Use formal tone."

    def test_style_upload_updates_document_summary(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)

        with patch("m_chat.api.extract_style_document", return_value="Use short sentences."):
            resp = client.post(
                f"/chat/{sid}/style/upload",
                files={"file": ("style_guide.txt", BytesIO(b"Use short sentences."), "text/plain")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "style_guide.txt"
        assert data["characters_extracted"] == len("Use short sentences.")

        # Verify it was saved in the style profile
        resp2 = client.get(f"/chat/{sid}/style", headers=headers)
        assert resp2.status_code == 200
        assert "Use short sentences." in resp2.json()["style_profile"]["document_summary"]


# ---------------------------------------------------------------------------
# TestDocumentUpload
# ---------------------------------------------------------------------------


class TestDocumentUpload:
    def test_upload_txt_returns_topic_summary(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        extracted_text = "This document covers student wellbeing metrics."

        with patch("m_chat.api.document_to_markdown", return_value=extracted_text):
            resp = client.post(
                f"/chat/{sid}/upload",
                files={"file": ("data.txt", BytesIO(b"raw content"), "text/plain")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "data.txt"
        assert data["characters_extracted"] == len(extracted_text)
        # No LLM → fallback summary is first 200 chars of extracted
        assert data["topic_summary"] == extracted_text[:200]

    def test_upload_unsupported_type_returns_422(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.post(
            f"/chat/{sid}/upload",
            files={"file": ("data.csv", BytesIO(b"a,b,c"), "text/csv")},
            headers=headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestScenarioIntegration
# ---------------------------------------------------------------------------


class TestScenarioIntegration:
    def test_scenario_scratch_to_export(self, client_with_llm, jwt_secret, mock_llm):
        """Create session → plain chat → survey-update chat → GET survey → export."""
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)

        # Turn 1: plain text response
        mock_llm.create_completion.return_value = "Let's start with the basics."
        r1 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "I need a wellbeing survey."},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["survey_updated"] is False

        # Turn 2: survey update
        survey_json = json.dumps(SAMPLE_SURVEY_DICT)
        mock_llm.create_completion.return_value = (
            f"Here's a draft.<survey_update>{survey_json}</survey_update>"
        )
        r2 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create the survey now."},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["survey_updated"] is True

        # GET survey
        r3 = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert r3.status_code == 200
        survey = r3.json()["survey"]
        assert survey is not None
        assert survey["title"] == "Test Survey"

        # Export to LimeSurvey
        r4 = client_with_llm.post(
            "/export",
            json={"format": "limesurvey", "survey": survey},
            headers=headers,
        )
        assert r4.status_code == 200
        assert "<document>" in r4.json()["content"]

    def test_scenario_session_isolation(self, client, jwt_secret):
        """User1's session must be invisible and inaccessible to user2."""
        h1 = _make_auth_headers("user1")
        h2 = _make_auth_headers("user2")

        sid1 = _create_chat_session(client, h1)

        # user2 cannot GET user1's session
        assert client.get(f"/chat/{sid1}", headers=h2).status_code == 403
        # user2 cannot DELETE user1's session
        assert client.delete(f"/chat/{sid1}", headers=h2).status_code == 403
        # user2 cannot POST to user1's session
        assert client.post(f"/chat/{sid1}/reset", headers=h2).status_code == 403

        # user2's session list does not include user1's session
        r = client.get("/chat/sessions", headers=h2)
        assert r.status_code == 200
        ids = [s["session_id"] for s in r.json()["sessions"]]
        assert sid1 not in ids

        # user1's session list does include sid1
        r2 = client.get("/chat/sessions", headers=h1)
        assert r2.status_code == 200
        ids2 = [s["session_id"] for s in r2.json()["sessions"]]
        assert sid1 in ids2

    def test_scenario_session_resume(self, app, jwt_secret, mock_llm, session_manager):
        """Session state (conversation + draft) persists across client instances."""
        headers = _make_auth_headers("user1")

        # Client A: create session and send a message
        mock_llm.create_completion.return_value = "Hello!"
        app_with_llm = create_app(session_manager=session_manager, llm_client=mock_llm)
        app_with_llm.add_middleware(
            SessionMiddleware, session_manager=session_manager, ttl_hours=24
        )
        client_a = TestClient(app_with_llm, raise_server_exceptions=False)
        sid = _create_chat_session(client_a, headers)

        survey_json = json.dumps(SAMPLE_SURVEY_DICT)
        mock_llm.create_completion.return_value = (
            f"Here it is.<survey_update>{survey_json}</survey_update>"
        )
        client_a.post(f"/chat/{sid}", json={"message": "Create a survey."}, headers=headers)

        # Client B: new TestClient, same session_manager (same tmp_path)
        app_b = create_app(session_manager=session_manager)
        app_b.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        client_b = TestClient(app_b, raise_server_exceptions=False)

        # Session metadata is still accessible
        r_meta = client_b.get(f"/chat/{sid}", headers=headers)
        assert r_meta.status_code == 200
        assert r_meta.json()["session_id"] == sid

        # Draft survey persists
        r_survey = client_b.get(f"/chat/{sid}/survey", headers=headers)
        assert r_survey.status_code == 200
        assert r_survey.json()["survey"] is not None
        assert r_survey.json()["survey"]["title"] == "Test Survey"
