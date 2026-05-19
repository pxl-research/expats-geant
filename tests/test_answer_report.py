"""Tests for per-session answer_report.json persistence and download endpoint."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from cue_api.ingest import ingest_files_into_store
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
    app = create_app(session_manager=session_manager, llm_client=mock_llm)
    app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_token(jwt_secret):
    return create_token(
        user_id="test_user",
        session_id="dev_session_test_user",
        org="test_org",
        roles=["respondent"],
    )


def _seed_doc(tmp_path, session_manager, auth_token):
    """Create a session, ingest a document, and return the session."""
    doc = tmp_path / "doc.txt"
    doc.write_text("Data is retained for 36 months. Annual audits are conducted in Q3.")
    session = session_manager.create_session(
        user_id="test_user", explicit_session_id="dev_session_test_user"
    )
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(file_paths=[str(doc)], store=store, session_id=session.session_id)
    return session


class TestSingleSuggestionCreatesReport:
    """6.1 — POST /suggest/batch creates answer_report.json with expected keys."""

    def test_single_suggestion_creates_report(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        session = _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "36 months.", "reasoning": "Policy document states this."}'
        )

        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [
                    {
                        "id": "q1",
                        "type": "open_ended",
                        "prompt": "What is our data retention period?",
                        "choices": [],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        report_path = session_manager._get_session_path(session.session_id) / "answer_report.json"
        assert report_path.exists(), "answer_report.json should be created after /suggest"

        entries = [
            json.loads(line) for line in report_path.read_text().splitlines() if line.strip()
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert "question" in entry
        assert "answer" in entry
        assert "reasoning" in entry
        assert "citations" in entry
        assert entry["question"] == "What is our data retention period?"
        assert entry["answer"] == "36 months."


class TestMultipleSuggestionsAccumulate:
    """6.2 — Two POST /suggest/batch calls accumulate in answer_report.json."""

    def test_multiple_suggestions_accumulate(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        session = _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "Yes.", "reasoning": "Evidence found."}'
        )

        batch1 = {
            "assessment_id": "test-1",
            "items": [
                {"id": "q1", "type": "open_ended", "prompt": "Do we conduct annual audits?"},
                {"id": "q2", "type": "open_ended", "prompt": "How long is data retained?"},
            ],
        }
        resp1 = client.post(
            "/suggest/batch",
            json=batch1,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp1.status_code == 200

        batch2 = {
            "assessment_id": "test-2",
            "items": [
                {"id": "q3", "type": "open_ended", "prompt": "Who is the data controller?"},
            ],
        }
        resp2 = client.post(
            "/suggest/batch",
            json=batch2,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp2.status_code == 200

        report_path = session_manager._get_session_path(session.session_id) / "answer_report.json"
        assert report_path.exists()
        entries = [
            json.loads(line) for line in report_path.read_text().splitlines() if line.strip()
        ]
        assert len(entries) == 3  # 2 from batch1 + 1 from batch2


class TestDownloadEndpoint:
    """6.3a — GET /answer-report/download returns 200 with file when suggestions exist."""

    def test_download_returns_file_when_suggestions_exist(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "Q3.", "reasoning": "Stated in policy."}'
        )

        client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [
                    {
                        "id": "q1",
                        "type": "open_ended",
                        "prompt": "When are audits conducted?",
                        "choices": [],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        resp = client.get(
            "/answer-report/download",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        entry = data[0]
        assert entry["question"] == "When are audits conducted?"
        assert "answer" in entry
        assert "reasoning" in entry
        assert "citations" in entry

    def test_download_returns_404_when_no_suggestions(self, client, auth_token, session_manager):
        """6.3b — Fresh session with no suggestions → 404."""
        # Trigger session creation via a stats call
        client.get("/session/stats", headers={"Authorization": f"Bearer {auth_token}"})

        resp = client.get(
            "/answer-report/download",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


class TestSuggestionCacheCreated:
    """Batch suggest creates cached_suggestions.json alongside answer_report."""

    def test_batch_suggest_creates_cache(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        session = _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "36 months.", "reasoning": "Policy states this."}'
        )

        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [
                    {
                        "id": "q1",
                        "type": "open_ended",
                        "prompt": "Retention period?",
                        "choices": [],
                    },
                    {"id": "q2", "type": "open_ended", "prompt": "Audit frequency?", "choices": []},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        cache_path = (
            session_manager._get_session_path(session.session_id) / "cached_suggestions.json"
        )
        assert cache_path.exists()
        cache = json.loads(cache_path.read_text())
        assert "q1" in cache
        assert "q2" in cache
        assert cache["q1"]["item_id"] == "q1"
        assert cache["q1"]["suggestion"] == "36 months."
        assert "citations" in cache["q1"]

    def test_cache_has_full_item_suggestion_fields(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "Yes.", "reasoning": "Found evidence."}'
        )

        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "Do we audit?", "choices": []},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        resp = client.get("/cached-suggestions", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        data = resp.json()["suggestions"]
        assert "q1" in data
        sug = data["q1"]
        assert sug["type"] == "open_ended"
        assert sug["suggestion"] == "Yes."
        assert sug["reasoning"] == "Found evidence."
        assert isinstance(sug["citations"], list)

    def test_cache_accumulates_across_batches(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = '{"answer": "A.", "reasoning": "R."}'

        client.post(
            "/suggest/batch",
            json={
                "assessment_id": "t1",
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "Q1?", "choices": []},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        client.post(
            "/suggest/batch",
            json={
                "assessment_id": "t2",
                "items": [
                    {"id": "q2", "type": "open_ended", "prompt": "Q2?", "choices": []},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        resp = client.get("/cached-suggestions", headers={"Authorization": f"Bearer {auth_token}"})
        data = resp.json()["suggestions"]
        assert "q1" in data
        assert "q2" in data


class TestReportDeletedWithSession:
    """6.4 — DELETE /session removes the entire session directory including the report."""

    def test_report_deleted_with_session(
        self, client, auth_token, tmp_path, session_manager, mock_llm
    ):
        session = _seed_doc(tmp_path, session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "36 months.", "reasoning": "Policy states this."}'
        )

        client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "Retention period?", "choices": []}
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        session_path = session_manager._get_session_path(session.session_id)
        assert session_path.exists()

        resp = client.delete("/session", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200

        assert not session_path.exists(), "Session directory (including report) should be deleted"
