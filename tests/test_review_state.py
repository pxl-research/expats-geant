"""Tests for server-side review state persistence."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _session_path(session_manager, auth_token):
    session = session_manager.create_session(user_id="test_user", jwt_token=auth_token)
    return session_manager._get_session_path(session.session_id)


class TestPutReviewState:
    def test_save_accepted(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "36 months"},
            headers=_auth(auth_token),
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_save_dismissed(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.put(
            "/review-state/q2",
            json={"state": "dismissed"},
            headers=_auth(auth_token),
        )
        assert resp.status_code == 200

    def test_save_edited_with_selected_id(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.put(
            "/review-state/q3",
            json={"state": "edited", "selected_id": "opt-b"},
            headers=_auth(auth_token),
        )
        assert resp.status_code == 200

    def test_save_edited_with_selected_ids(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.put(
            "/review-state/q4",
            json={"state": "edited", "selected_ids": ["opt-a", "opt-c"]},
            headers=_auth(auth_token),
        )
        assert resp.status_code == 200

    def test_invalid_state_rejected(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.put(
            "/review-state/q1",
            json={"state": "invalid"},
            headers=_auth(auth_token),
        )
        assert resp.status_code == 422

    def test_state_written_to_disk(self, client, auth_token, session_manager):
        sp = _session_path(session_manager, auth_token)
        client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "hello"},
            headers=_auth(auth_token),
        )
        review_path = sp / "review_state.json"
        assert review_path.exists()
        data = json.loads(review_path.read_text())
        assert data["q1"]["state"] == "accepted"
        assert data["q1"]["value"] == "hello"


class TestGetReviewState:
    def test_empty_session(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.get("/review-state", headers=_auth(auth_token))
        assert resp.status_code == 200
        assert resp.json() == {"states": {}}

    def test_after_put(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "yes"},
            headers=_auth(auth_token),
        )
        resp = client.get("/review-state", headers=_auth(auth_token))
        assert resp.status_code == 200
        states = resp.json()["states"]
        assert "q1" in states
        assert states["q1"]["state"] == "accepted"
        assert states["q1"]["value"] == "yes"


class TestOverwriteState:
    def test_second_put_overwrites(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "first"},
            headers=_auth(auth_token),
        )
        client.put(
            "/review-state/q1",
            json={"state": "edited", "value": "second"},
            headers=_auth(auth_token),
        )
        resp = client.get("/review-state", headers=_auth(auth_token))
        states = resp.json()["states"]
        assert states["q1"]["state"] == "edited"
        assert states["q1"]["value"] == "second"


class TestMultipleQuestions:
    def test_multiple_questions_coexist(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "yes"},
            headers=_auth(auth_token),
        )
        client.put(
            "/review-state/q2",
            json={"state": "dismissed"},
            headers=_auth(auth_token),
        )
        client.put(
            "/review-state/q3",
            json={"state": "edited", "selected_id": "opt-x"},
            headers=_auth(auth_token),
        )
        resp = client.get("/review-state", headers=_auth(auth_token))
        states = resp.json()["states"]
        assert len(states) == 3
        assert states["q1"]["state"] == "accepted"
        assert states["q2"]["state"] == "dismissed"
        assert states["q3"]["state"] == "edited"


class TestSessionDeleteCleansUp:
    def test_delete_removes_review_state(self, client, auth_token, session_manager):
        sp = _session_path(session_manager, auth_token)
        client.put(
            "/review-state/q1",
            json={"state": "accepted", "value": "test"},
            headers=_auth(auth_token),
        )
        assert (sp / "review_state.json").exists()

        client.delete("/session", headers=_auth(auth_token))
        assert not sp.exists()


class TestReviewStateAuth:
    def test_unauthenticated_put(self, client):
        resp = client.put("/review-state/q1", json={"state": "accepted"})
        assert resp.status_code == 401

    def test_unauthenticated_get(self, client):
        resp = client.get("/review-state")
        assert resp.status_code == 401


class TestAnswerReportEnrichment:
    """Answer report download includes review state when present."""

    def _seed_answer_report(self, session_manager, auth_token):
        session = session_manager.create_session(user_id="test_user", jwt_token=auth_token)
        sp = session_manager._get_session_path(session.session_id)
        report_path = sp / "answer_report.json"
        entries = [
            {"question_id": "q1", "question": "Q1?", "answer": "A1", "generated_at": "2026-01-01"},
            {"question_id": "q2", "question": "Q2?", "answer": "A2", "generated_at": "2026-01-01"},
            {"question_id": "q3", "question": "Q3?", "answer": "A3", "generated_at": "2026-01-01"},
        ]
        with open(report_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return sp

    def test_enriched_with_review_state(self, client, auth_token, session_manager):
        sp = self._seed_answer_report(session_manager, auth_token)
        review_state = {
            "q1": {"state": "accepted", "value": "Final A1"},
            "q2": {"state": "dismissed"},
        }
        (sp / "review_state.json").write_text(json.dumps(review_state))

        resp = client.get("/answer-report/download", headers=_auth(auth_token))
        assert resp.status_code == 200
        data = resp.json()

        assert data[0]["review_state"] == "accepted"
        assert data[0]["final_value"] == "Final A1"

        assert data[1]["review_state"] == "dismissed"
        assert data[1]["final_value"] is None

        assert "review_state" not in data[2]
        assert "final_value" not in data[2]

    def test_no_review_state_file(self, client, auth_token, session_manager):
        self._seed_answer_report(session_manager, auth_token)
        resp = client.get("/answer-report/download", headers=_auth(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        for entry in data:
            assert "review_state" not in entry
            assert "final_value" not in entry

    def test_accepted_without_value_falls_back_to_answer(self, client, auth_token, session_manager):
        sp = self._seed_answer_report(session_manager, auth_token)
        review_state = {"q1": {"state": "accepted"}}
        (sp / "review_state.json").write_text(json.dumps(review_state))

        resp = client.get("/answer-report/download", headers=_auth(auth_token))
        data = resp.json()
        assert data[0]["final_value"] == "A1"

    def test_edited_with_selected_id(self, client, auth_token, session_manager):
        sp = self._seed_answer_report(session_manager, auth_token)
        review_state = {"q1": {"state": "edited", "selected_id": "opt-b"}}
        (sp / "review_state.json").write_text(json.dumps(review_state))

        resp = client.get("/answer-report/download", headers=_auth(auth_token))
        data = resp.json()
        assert data[0]["review_state"] == "edited"
        assert data[0]["final_value"] == "opt-b"

    def test_edited_with_selected_ids(self, client, auth_token, session_manager):
        sp = self._seed_answer_report(session_manager, auth_token)
        review_state = {"q3": {"state": "edited", "selected_ids": ["opt-a", "opt-c"]}}
        (sp / "review_state.json").write_text(json.dumps(review_state))

        resp = client.get("/answer-report/download", headers=_auth(auth_token))
        data = resp.json()
        assert data[2]["review_state"] == "edited"
        assert data[2]["final_value"] == ["opt-a", "opt-c"]


class TestCachedSuggestions:
    def test_empty_session_returns_empty(self, client, auth_token, session_manager):
        _session_path(session_manager, auth_token)
        resp = client.get("/cached-suggestions", headers=_auth(auth_token))
        assert resp.status_code == 200
        assert resp.json() == {"suggestions": {}}

    def test_cached_suggestions_returned(self, client, auth_token, session_manager):
        sp = _session_path(session_manager, auth_token)
        cache = {
            "q1": {
                "item_id": "q1",
                "type": "open_ended",
                "suggestion": "36 months",
                "reasoning": "Policy states this",
                "selected_id": None,
                "selected_ids": None,
                "citations": [],
            }
        }
        (sp / "cached_suggestions.json").write_text(json.dumps(cache))

        resp = client.get("/cached-suggestions", headers=_auth(auth_token))
        assert resp.status_code == 200
        data = resp.json()["suggestions"]
        assert "q1" in data
        assert data["q1"]["suggestion"] == "36 months"

    def test_session_delete_removes_cache(self, client, auth_token, session_manager):
        sp = _session_path(session_manager, auth_token)
        (sp / "cached_suggestions.json").write_text('{"q1": {}}')
        assert (sp / "cached_suggestions.json").exists()

        client.delete("/session", headers=_auth(auth_token))
        assert not sp.exists()

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/cached-suggestions")
        assert resp.status_code == 401
