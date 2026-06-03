"""Integration tests for shape_api/api.py endpoints.

Covers:
- Public endpoints (/ and /health)
- Auth failures (missing/expired token → 401)
- POST /import: valid LSS XML → Survey JSON
- POST /export: Survey dict + format → file content
- POST /export: unknown format → 422
- POST /create: no credentials → file_export fallback
- POST /suggest: without LLM → 500; with mock LLM → suggestions
- POST /suggest: with valid session_id → style context used
- POST /suggest: with foreign session_id → 403
- POST /validate: question only → issues list (no LLM)
- POST /validate: survey → all questions covered
- POST /validate: neither question nor survey → 422
- POST /tag: no session_id → tags returned, vocabulary NOT updated
- POST /tag: with session_id → vocabulary updated
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager
from shape_api.api import create_app

# ---------------------------------------------------------------------------
# Sample payloads
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

SAMPLE_QUESTION_DICT = {
    "id": "q1",
    "text": "How satisfied are you with the service?",
    "type": "open_ended",
    "order": 0,
    "answer_options": [],
    "required": False,
    "min_value": None,
    "max_value": None,
    "step": None,
    "metadata": {},
}

# Survey with a double-barreled question (triggers tier-1 validation issue)
SURVEY_WITH_ISSUES_DICT = {
    "id": "s2",
    "title": "Survey With Issues",
    "description": "",
    "sections": [
        {
            "id": "sec1",
            "title": "Section 1",
            "description": "",
            "questions": [
                {
                    "id": "q1",
                    "text": "Do you like the product and the service?",
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
# Fixtures
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
    llm.create_completion.return_value = json.dumps(
        [
            {"phrasing": "Improved phrasing 1", "reasoning": "Clearer"},
            {"phrasing": "Improved phrasing 2", "reasoning": "More concise"},
            {"phrasing": "Improved phrasing 3", "reasoning": "Less biased"},
        ]
    )
    return llm


@pytest.fixture
def app_with_llm(session_manager, jwt_secret, mock_llm):
    application = create_app(session_manager=session_manager, llm_client=mock_llm)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def auth_token(jwt_secret):
    return create_token(
        user_id="test_user",
        session_id="test_session",
        org="test_org",
        roles=["user"],
    )


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_llm(app_with_llm):
    return TestClient(app_with_llm, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


class TestPublicEndpoints:
    def test_root_no_auth_required(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "shape-api"

    def test_health_no_auth_required(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Auth failures
# ---------------------------------------------------------------------------


class TestAuthFailures:
    def test_missing_token_returns_401(self, client):
        response = client.post("/suggest", json={"question": SAMPLE_QUESTION_DICT})
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client, monkeypatch, jwt_secret):
        monkeypatch.setenv("JWT_EXPIRATION_HOURS", "0")
        expired = create_token(
            user_id="test_user",
            session_id="test_session",
            org="org",
            roles=["user"],
        )
        monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_missing_bearer_prefix_returns_401(self, client, auth_token):
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers={"Authorization": auth_token},  # no "Bearer" prefix
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /import
# ---------------------------------------------------------------------------


class TestImportEndpoint:
    def test_import_limesurvey_returns_survey_json(self, client, auth_headers):
        response = client.post(
            "/import",
            json={"format": "limesurvey", "content": MINIMAL_LSS},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "survey" in data
        assert data["survey"]["title"] == "Test Survey"

    def test_import_lss_format_alias(self, client, auth_headers):
        response = client.post(
            "/import",
            json={"format": "lss", "content": MINIMAL_LSS},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "survey" in response.json()

    def test_import_invalid_content_returns_400(self, client, auth_headers):
        response = client.post(
            "/import",
            json={"format": "limesurvey", "content": "not valid xml"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_import_unknown_format_returns_422(self, client, auth_headers):
        response = client.post(
            "/import",
            json={"format": "unknown_format", "content": MINIMAL_LSS},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_import_survey_has_sections(self, client, auth_headers):
        response = client.post(
            "/import",
            json={"format": "limesurvey", "content": MINIMAL_LSS},
            headers=auth_headers,
        )
        assert response.status_code == 200
        survey = response.json()["survey"]
        assert len(survey["sections"]) >= 1


# ---------------------------------------------------------------------------
# POST /export
# ---------------------------------------------------------------------------


class TestExportEndpoint:
    def test_export_limesurvey_returns_xml(self, client, auth_headers):
        response = client.post(
            "/export",
            json={"format": "limesurvey", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "limesurvey"
        assert "<document>" in data["content"]

    def test_export_qti_returns_xml(self, client, auth_headers):
        response = client.post(
            "/export",
            json={"format": "qti", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "<assessmentTest" in response.json()["content"]

    def test_export_surveymonkey_returns_json(self, client, auth_headers):
        response = client.post(
            "/export",
            json={"format": "surveymonkey", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        content = response.json()["content"]
        data = json.loads(content)
        assert data["title"] == SAMPLE_SURVEY_DICT["title"]

    def test_export_unknown_format_returns_422(self, client, auth_headers):
        response = client.post(
            "/export",
            json={"format": "bogus_format", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_export_invalid_survey_returns_422(self, client, auth_headers):
        response = client.post(
            "/export",
            json={"format": "limesurvey", "survey": {"bad": "data"}},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /create
# ---------------------------------------------------------------------------


class TestCreateEndpoint:
    def test_create_no_credentials_returns_file_export(self, client, auth_headers):
        response = client.post(
            "/create",
            json={"format": "limesurvey", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_via"] == "file_export"
        assert data["format"] == "limesurvey"
        assert len(data["platform_id"]) > 0

    def test_create_qti_no_credentials_returns_file_export(self, client, auth_headers):
        response = client.post(
            "/create",
            json={"format": "qti", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["created_via"] == "file_export"
        assert "<assessmentTest" in response.json()["platform_id"]

    def test_create_surveymonkey_no_credentials_returns_file_export(self, client, auth_headers):
        response = client.post(
            "/create",
            json={"format": "surveymonkey", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["created_via"] == "file_export"

    def test_create_unknown_format_returns_422(self, client, auth_headers):
        response = client.post(
            "/create",
            json={"format": "unknown", "survey": SAMPLE_SURVEY_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_invalid_survey_returns_422(self, client, auth_headers):
        response = client.post(
            "/create",
            json={"format": "limesurvey", "survey": {}},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_surfaces_adapter_runtime_error_as_502(self, client, auth_headers, monkeypatch):
        """An upstream adapter failure (e.g. wrong LimeSurvey credentials)
        must arrive at the UI with the actual message intact, not as a
        generic 500. Routes that swallow the message break the user-facing
        error rendering."""
        from m_shared.adapters.limesurvey import LimeSurveyAdapter

        def fake_create_survey(self, survey):
            raise RuntimeError("LimeSurvey authentication failed: Invalid user name or password")

        monkeypatch.setattr(LimeSurveyAdapter, "create_survey", fake_create_survey)
        response = client.post(
            "/create",
            json={
                "format": "limesurvey",
                "survey": SAMPLE_SURVEY_DICT,
                "api_url": "http://host.docker.internal:7080/index.php/admin/remotecontrol",
                "username": "admin",
                "password": "wrong",
            },
            headers=auth_headers,
        )
        assert response.status_code == 502
        assert "Invalid user name or password" in response.json()["detail"]

    def test_create_surfaces_adapter_value_error_as_400(self, client, auth_headers, monkeypatch):
        """ValueError from the adapter (e.g. credentials missing) maps to 400
        with the adapter's own message."""
        from m_shared.adapters.limesurvey import LimeSurveyAdapter

        def fake_create_survey(self, survey):
            raise ValueError(
                "LimeSurvey API URL, username, and password must be set to create surveys."
            )

        monkeypatch.setattr(LimeSurveyAdapter, "create_survey", fake_create_survey)
        response = client.post(
            "/create",
            json={
                "format": "limesurvey",
                "survey": SAMPLE_SURVEY_DICT,
                "api_url": "http://host.docker.internal:7080/index.php/admin/remotecontrol",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "must be set" in response.json()["detail"]

    def test_create_falls_back_to_file_export_on_not_implemented(
        self, client, auth_headers, monkeypatch
    ):
        """NotImplementedError is the documented contract for 'no API write
        support' — should fall back to file_export rather than raising."""
        from m_shared.adapters.limesurvey import LimeSurveyAdapter

        def fake_create_survey(self, survey):
            raise NotImplementedError

        monkeypatch.setattr(LimeSurveyAdapter, "create_survey", fake_create_survey)
        response = client.post(
            "/create",
            json={
                "format": "limesurvey",
                "survey": SAMPLE_SURVEY_DICT,
                "api_url": "http://host.docker.internal:7080/index.php/admin/remotecontrol",
                "username": "admin",
                "password": "changeme",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["created_via"] == "file_export"


# ---------------------------------------------------------------------------
# POST /suggest
# ---------------------------------------------------------------------------


class TestSuggestEndpoint:
    def test_suggest_without_llm_returns_500(self, client, auth_headers):
        """No LLM configured → 500."""
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 500

    def test_suggest_with_mock_llm_returns_suggestions(self, client_with_llm, auth_headers):
        response = client_with_llm.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0
        assert "phrasing" in data["suggestions"][0]

    def test_suggest_suggestions_have_reasoning(self, client_with_llm, auth_headers):
        response = client_with_llm.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        for s in response.json()["suggestions"]:
            assert "reasoning" in s

    def test_suggest_custom_n_suggestions(self, client_with_llm, auth_headers, mock_llm):
        mock_llm.create_completion.return_value = json.dumps(
            [{"phrasing": "Only one", "reasoning": ""}]
        )
        response = client_with_llm.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT, "n_suggestions": 1},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_suggest_with_session_id_loads_context(
        self, app_with_llm, session_manager, jwt_secret, mock_llm
    ):
        """session_id provided → style_profile context is loaded and passed to engine."""
        # Create a chat session with a style profile
        session = session_manager.create_session(
            user_id="test_user",
            explicit_session_id="chat_sess_1",
        )
        style_path = (
            session_manager._get_session_path(session.session_id, user_id="test_user")
            / "style_profile.json"
        )
        style_path.write_text(json.dumps({"language": "fr", "free_text": "formal"}))

        client = TestClient(app_with_llm, raise_server_exceptions=False)
        auth = create_token(
            user_id="test_user", session_id="test_session", org="org", roles=["user"]
        )
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT, "session_id": "chat_sess_1"},
            headers={"Authorization": f"Bearer {auth}"},
        )
        assert response.status_code == 200
        # Verify the LLM was called (style context was used)
        mock_llm.create_completion.assert_called()

    def test_suggest_with_foreign_session_id_returns_403(
        self, app_with_llm, session_manager, jwt_secret
    ):
        """session_id belonging to another user → 403."""
        session_manager.create_session(
            user_id="other_user",
            explicit_session_id="foreign_sess",
        )
        client = TestClient(app_with_llm, raise_server_exceptions=False)
        auth = create_token(
            user_id="test_user", session_id="test_session", org="org", roles=["user"]
        )
        response = client.post(
            "/suggest",
            json={"question": SAMPLE_QUESTION_DICT, "session_id": "foreign_sess"},
            headers={"Authorization": f"Bearer {auth}"},
        )
        assert response.status_code == 403

    def test_suggest_invalid_question_returns_422(self, client_with_llm, auth_headers):
        response = client_with_llm.post(
            "/suggest",
            json={"question": {"bad": "data"}},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /validate
# ---------------------------------------------------------------------------


class TestValidateEndpoint:
    def test_validate_question_only_returns_issues(self, client, auth_headers):
        """Deterministic tier-1 validation works without LLM."""
        response = client.post(
            "/validate",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "issues" in data
        assert isinstance(data["issues"], list)

    def test_validate_question_with_issue_detected(self, client, auth_headers):
        """Double-barreled question should trigger a tier-1 warning."""
        double_barreled = {
            **SAMPLE_QUESTION_DICT,
            "text": "Do you like the product and the service?",
        }
        response = client.post(
            "/validate",
            json={"question": double_barreled},
            headers=auth_headers,
        )
        assert response.status_code == 200
        issues = response.json()["issues"]
        codes = [i["code"] for i in issues]
        assert "double_barreled" in codes

    def test_validate_survey_returns_issues_for_all_questions(self, client, auth_headers):
        response = client.post(
            "/validate",
            json={"survey": SURVEY_WITH_ISSUES_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        issues = response.json()["issues"]
        assert isinstance(issues, list)

    def test_validate_neither_question_nor_survey_returns_422(self, client, auth_headers):
        response = client.post(
            "/validate",
            json={"session_id": None},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_validate_issue_has_required_fields(self, client, auth_headers):
        double_barreled = {
            **SAMPLE_QUESTION_DICT,
            "text": "Do you like the product and the service?",
        }
        response = client.post(
            "/validate",
            json={"question": double_barreled},
            headers=auth_headers,
        )
        issues = response.json()["issues"]
        if issues:
            issue = issues[0]
            assert "question_id" in issue
            assert "severity" in issue
            assert "code" in issue
            assert "message" in issue

    def test_validate_clean_question_returns_no_issues(self, client, auth_headers):
        clean_question = {
            **SAMPLE_QUESTION_DICT,
            "text": "How would you rate this product?",
        }
        response = client.post(
            "/validate",
            json={"question": clean_question},
            headers=auth_headers,
        )
        assert response.status_code == 200
        # May or may not have issues, but should not error

    def test_validate_missing_auth_returns_401(self, client):
        response = client.post("/validate", json={"question": SAMPLE_QUESTION_DICT})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /tag
# ---------------------------------------------------------------------------


class TestTagEndpoint:
    def test_tag_without_llm_returns_500(self, client, auth_headers):
        response = client.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 500

    def test_tag_with_mock_llm_returns_tags(self, client_with_llm, auth_headers, mock_llm):
        mock_llm.create_completion.return_value = json.dumps(["satisfaction", "service", "rating"])
        response = client_with_llm.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_tag_without_session_id_vocabulary_not_updated(
        self, client_with_llm, auth_headers, mock_llm
    ):
        mock_llm.create_completion.return_value = json.dumps(["tag1", "tag2"])
        response = client_with_llm.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["vocabulary_updated"] is False

    def test_tag_with_session_id_updates_vocabulary(
        self, app_with_llm, session_manager, jwt_secret, mock_llm
    ):
        """Providing session_id causes vocabulary to be updated and saved."""
        session_manager.create_session(
            user_id="test_user",
            explicit_session_id="tag_sess_1",
        )
        mock_llm.create_completion.return_value = json.dumps(["new-tag", "another-tag"])

        client = TestClient(app_with_llm, raise_server_exceptions=False)
        auth = create_token(
            user_id="test_user", session_id="test_session", org="org", roles=["user"]
        )
        response = client.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT, "session_id": "tag_sess_1"},
            headers={"Authorization": f"Bearer {auth}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["vocabulary_updated"] is True

        # Verify vocabulary file was written
        vocab_path = (
            session_manager._get_session_path("tag_sess_1", user_id="test_user")
            / "tag_vocabulary.json"
        )
        assert vocab_path.exists()
        vocab = json.loads(vocab_path.read_text())
        assert len(vocab) > 0

    def test_tag_tags_are_normalised(self, client_with_llm, auth_headers, mock_llm):
        mock_llm.create_completion.return_value = json.dumps(["Customer Service", "RATING"])
        response = client_with_llm.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT},
            headers=auth_headers,
        )
        assert response.status_code == 200
        tags = response.json()["tags"]
        for tag in tags:
            assert tag == tag.lower()

    def test_tag_with_foreign_session_returns_403(
        self, app_with_llm, session_manager, jwt_secret, mock_llm
    ):
        session_manager.create_session(
            user_id="other_user",
            explicit_session_id="foreign_tag_sess",
        )
        mock_llm.create_completion.return_value = json.dumps(["tag1"])
        client = TestClient(app_with_llm, raise_server_exceptions=False)
        auth = create_token(
            user_id="test_user", session_id="test_session", org="org", roles=["user"]
        )
        response = client.post(
            "/tag",
            json={"question": SAMPLE_QUESTION_DICT, "session_id": "foreign_tag_sess"},
            headers={"Authorization": f"Bearer {auth}"},
        )
        assert response.status_code == 403

    def test_tag_missing_auth_returns_401(self, client_with_llm):
        response = client_with_llm.post("/tag", json={"question": SAMPLE_QUESTION_DICT})
        assert response.status_code == 401
