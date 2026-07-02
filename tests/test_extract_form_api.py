"""Tests for the /extract-form endpoint (LLM-assisted form extraction)."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.client import LLMClient
from m_shared.session.manager import SessionManager
from m_shared.utils.audit import AuditEventType, AuditLogger


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
def audit_logger(tmp_path):
    return AuditLogger(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def mock_llm():
    client = MagicMock(spec=LLMClient)
    client.model_name = "mock-model"
    return client


@pytest.fixture
def app(session_manager, mock_llm, audit_logger):
    app = create_app(session_manager, llm_client=mock_llm, audit_logger=audit_logger)
    app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def valid_token(jwt_secret):
    return create_token(
        user_id="test_user_123",
        session_id="test_session_456",
        org="test_org",
        roles=["respondent"],
    )


@pytest.fixture
def auth_headers(valid_token):
    return {"Authorization": f"Bearer {valid_token}"}


def _body(url: str = "https://example.test/form", text: str = "Form\nName:\n") -> dict:
    return {"url": url, "page_text": text}


class TestAuth:
    def test_requires_authorization(self, client):
        response = client.post("/extract-form", json=_body())
        assert response.status_code == 401

    def test_rejects_invalid_token(self, client):
        response = client.post(
            "/extract-form",
            json=_body(),
            headers={"Authorization": "Bearer bogus"},
        )
        assert response.status_code == 401


class TestHappyPath:
    def test_returns_validated_items(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = json.dumps(
            {
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "Full name"},
                    {
                        "id": "q2",
                        "type": "single_choice",
                        "prompt": "Shift",
                        "choices": [
                            {"id": "c1", "label": "Morning"},
                            {"id": "c2", "label": "Evening"},
                        ],
                    },
                ]
            }
        )
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]["id"] == "q1"
        assert payload[0]["type"] == "open_ended"
        assert payload[1]["type"] == "single_choice"
        assert len(payload[1]["choices"]) == 2

    def test_drops_malformed_items_returns_valid_ones(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = json.dumps(
            {
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "Name"},
                    {"id": "q2", "type": "not_a_real_type", "prompt": "Bad"},
                    {"id": "q3", "type": "single_choice", "prompt": "No choices"},
                ]
            }
        )
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["id"] == "q1"

    def test_empty_items_list_returns_empty(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = json.dumps({"items": []})
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_llm_called_with_temperature_zero(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = json.dumps({"items": []})
        client.post("/extract-form", json=_body(), headers=auth_headers)
        _, kwargs = mock_llm.create_completion.call_args
        assert kwargs.get("temperature") == 0.0


class TestErrors:
    def test_llm_exception_returns_502(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.side_effect = RuntimeError("provider down")
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 502

    def test_unparseable_json_returns_502(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = "this is not json at all"
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 502

    def test_empty_response_returns_502(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = ""
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 502

    def test_response_without_items_key_returns_502(self, client, mock_llm, auth_headers):
        mock_llm.create_completion.return_value = json.dumps({"foo": "bar"})
        response = client.post("/extract-form", json=_body(), headers=auth_headers)
        assert response.status_code == 502

    def test_missing_url_rejected(self, client, auth_headers):
        response = client.post(
            "/extract-form",
            json={"page_text": "Hello"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_missing_page_text_rejected(self, client, auth_headers):
        response = client.post(
            "/extract-form",
            json={"url": "https://example.test/form"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_oversized_page_text_rejected(self, client, auth_headers):
        response = client.post(
            "/extract-form",
            json={"url": "https://example.test/form", "page_text": "x" * 200_001},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAudit:
    def test_audit_event_recorded_on_success(self, client, mock_llm, audit_logger, auth_headers):
        mock_llm.create_completion.return_value = json.dumps(
            {"items": [{"id": "q1", "type": "open_ended", "prompt": "Hi"}]}
        )
        response = client.post(
            "/extract-form",
            json=_body(url="https://example.test/voluntary"),
            headers=auth_headers,
        )
        assert response.status_code == 200

        events = [
            e
            for e in audit_logger.get_entries("test_session_456")
            if e.event_type == AuditEventType.EXTRACT_FORM
        ]
        assert len(events) == 1
        assert events[0].details["url"] == "https://example.test/voluntary"
        assert events[0].details["item_count"] == 1
        assert events[0].details["model"] == "mock-model"
        assert events[0].user_id == "test_user_123"

    def test_audit_event_with_zero_items_still_recorded(
        self, client, mock_llm, audit_logger, auth_headers
    ):
        mock_llm.create_completion.return_value = json.dumps({"items": []})
        client.post("/extract-form", json=_body(), headers=auth_headers)
        events = [
            e
            for e in audit_logger.get_entries("test_session_456")
            if e.event_type == AuditEventType.EXTRACT_FORM
        ]
        assert len(events) == 1
        assert events[0].details["item_count"] == 0

    def test_no_audit_event_on_llm_failure(self, client, mock_llm, audit_logger, auth_headers):
        mock_llm.create_completion.side_effect = RuntimeError("boom")
        client.post("/extract-form", json=_body(), headers=auth_headers)
        events = [
            e
            for e in audit_logger.get_entries("test_session_456")
            if e.event_type == AuditEventType.EXTRACT_FORM
        ]
        assert events == []

    def test_audit_does_not_leak_page_text_or_form_values(
        self, client, mock_llm, audit_logger, auth_headers
    ):
        mock_llm.create_completion.return_value = json.dumps(
            {
                "items": [
                    {
                        "id": "q1",
                        "type": "open_ended",
                        "prompt": "PII_PROMPT_MARKER_xyz",
                    }
                ]
            }
        )
        page_text = "PII_PAGE_MARKER_abc Some sensitive page content."
        client.post(
            "/extract-form",
            json={"url": "https://example.test", "page_text": page_text},
            headers=auth_headers,
        )

        entries = audit_logger.get_entries("test_session_456")
        for entry in entries:
            serialized = json.dumps(entry.model_dump(mode="json"))
            assert "PII_PAGE_MARKER_abc" not in serialized
            assert "PII_PROMPT_MARKER_xyz" not in serialized


class TestLLMNotConfigured:
    def test_returns_503_when_no_llm_client(
        self, session_manager, audit_logger, jwt_secret, valid_token
    ):
        bare_app = create_app(session_manager, llm_client=None, audit_logger=audit_logger)
        bare_app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        bare_client = TestClient(bare_app)
        response = bare_client.post(
            "/extract-form",
            json=_body(),
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 503
