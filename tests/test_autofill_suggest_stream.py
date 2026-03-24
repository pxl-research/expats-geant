"""Tests for POST /suggest/stream SSE endpoint."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from cue_api.rag_pipeline import RAGPipeline
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager


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
def mock_llm():
    llm = MagicMock()
    llm.model_name = "test-model"
    llm.temperature = 0.4
    return llm


@pytest.fixture
def app(session_manager, mock_llm):
    application = create_app(session_manager=session_manager, llm_client=mock_llm)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_token(jwt_secret, session_manager):
    sm_path = session_manager._get_session_path("test-session")
    sm_path.mkdir(parents=True, exist_ok=True)
    token = create_token(user_id="user1", session_id="test-session")
    return token


BATCH_PAYLOAD = {
    "assessment_id": "test-session",
    "items": [
        {"id": "q1", "type": "open_ended", "prompt": "Describe your role", "choices": []},
        {"id": "q2", "type": "open_ended", "prompt": "What is your title?", "choices": []},
    ],
}

_FAKE_RESULT_1: dict = {
    "item_id": "q1",
    "type": "open_ended",
    "suggestion": "Software Engineer",
    "selected_id": None,
    "selected_ids": None,
    "reasoning": "Based on doc.",
    "citations": [],
}

_FAKE_RESULT_2: dict = {
    "item_id": "q2",
    "type": "open_ended",
    "suggestion": "Senior Developer",
    "selected_id": None,
    "selected_ids": None,
    "reasoning": None,
    "citations": [],
}


async def _fake_stream(*args, **kwargs):
    yield _FAKE_RESULT_1
    yield _FAKE_RESULT_2


class TestSuggestStream:
    def test_returns_event_stream_content_type(self, client, auth_token):
        with patch.object(RAGPipeline, "suggest_batch_stream", _fake_stream):
            resp = client.post(
                "/suggest/stream",
                json=BATCH_PAYLOAD,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_emits_suggestion_events_with_valid_json(self, client, auth_token):
        with patch.object(RAGPipeline, "suggest_batch_stream", _fake_stream):
            resp = client.post(
                "/suggest/stream",
                json=BATCH_PAYLOAD,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        lines = resp.text.splitlines()
        event_lines = [line for line in lines if line.startswith("event:")]
        data_lines = [line for line in lines if line.startswith("data:") and line != "data: {}"]

        assert event_lines.count("event: suggestion") == 2
        assert any("event: done" in line for line in event_lines)

        suggestion_data = [json.loads(line[len("data:") :].strip()) for line in data_lines[:2]]
        item_ids = {d["item_id"] for d in suggestion_data}
        assert item_ids == {"q1", "q2"}
        assert any(d["suggestion"] == "Software Engineer" for d in suggestion_data)

    def test_ends_with_done_event(self, client, auth_token):
        with patch.object(RAGPipeline, "suggest_batch_stream", _fake_stream):
            resp = client.post(
                "/suggest/stream",
                json=BATCH_PAYLOAD,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        assert "event: done" in resp.text
        assert resp.text.strip().endswith("data: {}")

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/suggest/stream", json=BATCH_PAYLOAD)
        assert resp.status_code == 401

    def test_mid_stream_error_emits_error_event(self, client, auth_token):
        async def _stream_with_error(*args, **kwargs):
            yield _FAKE_RESULT_1
            raise RuntimeError("LLM blew up")

        with patch.object(RAGPipeline, "suggest_batch_stream", _stream_with_error):
            resp = client.post(
                "/suggest/stream",
                json=BATCH_PAYLOAD,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        # First suggestion emitted before the stream raised
        assert "Software Engineer" in resp.text
        # Stream-level error yields event: error and no event: done
        assert resp.status_code == 200
        assert "event: error" in resp.text
        assert "event: done" not in resp.text
