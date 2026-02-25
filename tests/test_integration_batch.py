"""Integration tests for POST /suggest/batch and reasoning field on POST /suggest."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from m_autofill.api import create_app
from m_shared.auth.jwt_handler import create_token
from m_shared.session.manager import SessionManager


@pytest.fixture
def tmp_session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path))


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.model_name = "test-model"
    llm.temperature = 0.4
    return llm


@pytest.fixture
def auth_token(tmp_session_manager):
    return create_token(
        user_id="test_user",
        session_id="dev_session_test_user",
        org="test_org",
        roles=["respondent"],
    )


@pytest.fixture
def client(tmp_session_manager, mock_llm):
    from m_shared.auth.middleware import SessionMiddleware

    app = create_app(session_manager=tmp_session_manager, llm_client=mock_llm)
    app.add_middleware(SessionMiddleware, session_manager=tmp_session_manager, ttl_hours=24)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /suggest — reasoning field
# ---------------------------------------------------------------------------


class TestSuggestReasoning:
    def test_suggest_response_includes_reasoning_field(
        self, client, auth_token, tmp_path, tmp_session_manager, mock_llm
    ):
        """reasoning field present on /suggest response (may be null)."""
        from m_autofill.ingest import ingest_files_into_store

        doc = tmp_path / "policy.txt"
        doc.write_text("Data is retained for 36 months after contract termination.")

        session = tmp_session_manager.create_session(user_id="test_user", jwt_token=auth_token)
        store = tmp_session_manager.get_vector_store(session.session_id)
        ingest_files_into_store(file_paths=[str(doc)], store=store, session_id=session.session_id)

        mock_llm.create_completion.return_value = (
            '{"answer": "36 months.", "reasoning": "The policy document states this clearly."}'
        )

        resp = client.post(
            "/suggest",
            json={"question": "What is our data retention period?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "reasoning" in data  # field must be present (may be null)

    def test_suggest_reasoning_populated_from_llm(
        self, client, auth_token, tmp_path, tmp_session_manager, mock_llm
    ):
        doc = tmp_path / "policy.txt"
        doc.write_text("Annual audits are conducted every Q3.")

        session = tmp_session_manager.create_session(user_id="test_user", jwt_token=auth_token)
        store = tmp_session_manager.get_vector_store(session.session_id)

        from m_autofill.ingest import ingest_files_into_store

        ingest_files_into_store(file_paths=[str(doc)], store=store, session_id=session.session_id)

        mock_llm.create_completion.return_value = (
            '{"answer": "Yes.", "reasoning": "The report confirms Q3 audits annually."}'
        )

        resp = client.post(
            "/suggest",
            json={"question": "Do we conduct annual audits?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["reasoning"] == "The report confirms Q3 audits annually."


# ---------------------------------------------------------------------------
# POST /suggest/batch
# ---------------------------------------------------------------------------


class TestBatchSuggestEndpoint:
    def _seed_doc(self, tmp_path, tmp_session_manager, auth_token):
        from m_autofill.ingest import ingest_files_into_store

        doc = tmp_path / "doc.txt"
        doc.write_text(
            "We retain data for 36 months. Annual audits are performed in Q3. We process health and contact data."
        )
        session = tmp_session_manager.create_session(user_id="test_user", jwt_token=auth_token)
        store = tmp_session_manager.get_vector_store(session.session_id)
        ingest_files_into_store(file_paths=[str(doc)], store=store, session_id=session.session_id)

    def test_batch_flat_items(self, client, auth_token, tmp_path, tmp_session_manager, mock_llm):
        self._seed_doc(tmp_path, tmp_session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "36 months.", "reasoning": "Clearly stated."}'
        )

        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test-flat",
                "items": [
                    {"id": "q1", "type": "open_ended", "prompt": "What is our retention period?"},
                    {"id": "q2", "type": "open_ended", "prompt": "When are audits performed?"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessment_id"] == "test-flat"
        assert len(data["responses"]) == 2
        assert data["responses"][0]["item_id"] == "q1"
        assert data["responses"][1]["item_id"] == "q2"

    def test_batch_response_structure(
        self, client, auth_token, tmp_path, tmp_session_manager, mock_llm
    ):
        self._seed_doc(tmp_path, tmp_session_manager, auth_token)
        mock_llm.create_completion.return_value = (
            '{"answer": "Yes.", "selected": "yes", "reasoning": "Evidence found."}'
        )

        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test-struct",
                "sections": [
                    {
                        "id": "s1",
                        "title": "Compliance",
                        "items": [
                            {
                                "id": "q1",
                                "type": "single_choice",
                                "prompt": "Do we conduct annual audits?",
                                "choices": [
                                    {"id": "yes", "label": "Yes"},
                                    {"id": "no", "label": "No"},
                                ],
                            }
                        ],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        r = resp.json()["responses"][0]
        assert "item_id" in r
        assert "suggestion" in r
        assert "reasoning" in r
        assert "citations" in r
        assert "selected_id" in r

    def test_batch_both_sections_and_items_rejected(self, client, auth_token, mock_llm):
        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "bad",
                "sections": [
                    {"id": "s1", "items": [{"id": "q1", "type": "open_ended", "prompt": "?"}]}
                ],
                "items": [{"id": "q2", "type": "open_ended", "prompt": "?"}],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422

    def test_batch_requires_auth(self, client):
        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "test",
                "items": [{"id": "q1", "type": "open_ended", "prompt": "?"}],
            },
        )
        assert resp.status_code == 401

    def test_batch_no_documents_returns_reasoning(self, client, auth_token, mock_llm):
        """When no docs uploaded, each item should have a reasoning explaining no evidence."""
        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "nodocs",
                "items": [{"id": "q1", "type": "open_ended", "prompt": "What is our policy?"}],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        r = resp.json()["responses"][0]
        assert r["reasoning"] is not None
        assert len(r["citations"]) == 0

    def test_batch_assessment_id_echoed(self, client, auth_token, mock_llm):
        mock_llm.create_completion.return_value = '{"answer": "N/A.", "reasoning": null}'
        resp = client.post(
            "/suggest/batch",
            json={
                "assessment_id": "my-survey-123",
                "items": [{"id": "q1", "type": "open_ended", "prompt": "?"}],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["assessment_id"] == "my-survey-123"
