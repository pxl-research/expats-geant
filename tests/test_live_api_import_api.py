"""Integration tests for POST /surveys/import-from-api endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from m_autofill.api import create_app
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey
from m_shared.session.manager import SessionManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret-key"


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def autofill_app(session_manager):
    a = create_app(session_manager)
    a.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return a


@pytest.fixture
def client(autofill_app):
    return TestClient(autofill_app, raise_server_exceptions=True)


@pytest.fixture
def valid_token(jwt_secret):
    return create_token(
        user_id="test_user", session_id="test_session", org="test_org", roles=["respondent"]
    )


def _make_survey(title="Test Survey", with_question=True) -> Survey:
    questions = (
        [
            Question(
                id="q_10",
                text="What is your name?",
                type=QuestionType.OPEN_ENDED,
                order=0,
                answer_options=[],
                required=False,
            )
        ]
        if with_question
        else []
    )
    return Survey(
        id="123",
        title=title,
        description="",
        sections=[
            Section(id="grp_1", title="Section 1", description="", questions=questions, order=0)
        ],
        metadata={"platform": "limesurvey"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestImportSurveyFromApi:
    def _auth(self, token):
        return {"Authorization": f"Bearer {token}"}

    @patch("m_shared.adapters.limesurvey.LimeSurveyAdapter.fetch_survey")
    def test_lss_import_success(self, mock_fetch, client, valid_token):
        """Valid LSS import → 200 with survey_id."""
        mock_fetch.return_value = _make_survey()
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={
                "format": "lss",
                "survey_id": "123",
                "api_url": "http://ls.example.com/rpc",
                "username": "admin",
                "password": "pw",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "survey_id" in data
        assert data["warning"] is None

    @patch("m_shared.adapters.qualtrics.QualtricsAdapter.fetch_survey")
    def test_qsf_import_success(self, mock_fetch, client, valid_token):
        """Valid QSF import → 200 with survey_id."""
        mock_fetch.return_value = _make_survey(title="Qualtrics Survey")
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={
                "format": "qsf",
                "survey_id": "SV_abc123",
                "api_token": "tok",
                "datacenter_id": "iad1",
            },
        )
        assert resp.status_code == 200
        assert "survey_id" in resp.json()

    @patch("m_shared.adapters.limesurvey.LimeSurveyAdapter.fetch_survey")
    def test_missing_credentials_returns_400(self, mock_fetch, client, valid_token):
        """ValueError from adapter (missing credentials) → 400."""
        mock_fetch.side_effect = ValueError("must be set")
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={"format": "lss", "survey_id": "123"},
        )
        assert resp.status_code == 400
        assert "must be set" in resp.json()["detail"]

    @patch("m_shared.adapters.limesurvey.LimeSurveyAdapter.fetch_survey")
    def test_network_failure_returns_502(self, mock_fetch, client, valid_token):
        """RuntimeError from adapter (network failure) → 502."""
        mock_fetch.side_effect = RuntimeError("connection refused")
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={
                "format": "lss",
                "survey_id": "123",
                "api_url": "http://x",
                "username": "u",
                "password": "p",
            },
        )
        assert resp.status_code == 502
        assert "Platform API call failed" in resp.json()["detail"]

    def test_unsupported_format_returns_422(self, client, valid_token):
        """format='qti' is not supported for live API import → 422."""
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={"format": "qti", "survey_id": "123"},
        )
        assert resp.status_code == 422
        assert "qti" in resp.json()["detail"]

    def test_unauthenticated_returns_401(self, client):
        """No auth token → 401."""
        resp = client.post(
            "/surveys/import-from-api",
            json={"format": "lss", "survey_id": "123"},
        )
        assert resp.status_code == 401

    @patch("m_shared.adapters.limesurvey.LimeSurveyAdapter.fetch_survey")
    def test_no_questions_returns_warning(self, mock_fetch, client, valid_token):
        """Survey with zero questions → warning message in response."""
        mock_fetch.return_value = _make_survey(with_question=False)
        resp = client.post(
            "/surveys/import-from-api",
            headers=self._auth(valid_token),
            json={
                "format": "lss",
                "survey_id": "123",
                "api_url": "http://x",
                "username": "u",
                "password": "p",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["warning"] is not None
