"""Tests for text snippet ingestion — ingest helper, API endpoint, and UI route."""

from unittest.mock import MagicMock

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from cue_api.api import create_app
from cue_api.ingest import ingest_text_into_store
from cue_ui.main import app as ui_app
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager
from m_shared.vectordb import ChromaDocumentStore

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
def autofill_client(autofill_app):
    return TestClient(autofill_app, raise_server_exceptions=True)


@pytest.fixture
def valid_token(jwt_secret):
    return create_token(
        user_id="test_user", session_id="test_session", org="test_org", roles=["respondent"]
    )


@pytest.fixture
def vector_store(tmp_path):
    store_path = tmp_path / "chroma"
    store_path.mkdir(parents=True, exist_ok=True)
    return ChromaDocumentStore(path=str(store_path))


# ---------------------------------------------------------------------------
# Unit tests: ingest_text_into_store
# ---------------------------------------------------------------------------


class TestIngestTextIntoStore:
    def test_chunks_and_stores_text(self, vector_store):
        """Non-empty text is chunked, stored, and metadata carries the label."""
        added = ingest_text_into_store(
            text="Hello world. This is a test snippet.",
            label="My CV",
            store=vector_store,
        )

        assert len(added) == 1
        results = vector_store.query(query_text="test snippet", n_results=3)
        assert len(results) > 0
        assert all(r["metadata"]["source"] == "My CV" for r in results)
        assert all("chunk_index" in r["metadata"] for r in results)
        assert all(r["metadata"].get("source_kind") == "text" for r in results)
        assert all(r["metadata"].get("source_mime") == "text/plain" for r in results)

    def test_duplicate_label_skipped(self, vector_store):
        """Submitting the same label twice → second call returns empty list."""
        ingest_text_into_store(text="First content.", label="My Notes", store=vector_store)
        added = ingest_text_into_store(text="Second content.", label="My Notes", store=vector_store)
        assert added == []

    def test_returns_collection_name(self, vector_store):
        """Return value is a list with one sanitized collection name."""
        added = ingest_text_into_store(text="Some text.", label="Project notes", store=vector_store)
        assert len(added) == 1
        assert added[0]  # non-empty string

    def test_audit_logger_called(self, vector_store):
        """Audit logger is called when provided."""
        mock_logger = MagicMock()
        ingest_text_into_store(
            text="Audit test.",
            label="audit-label",
            store=vector_store,
            session_id="sess-123",
            user_id="user-456",
            audit_logger=mock_logger,
        )
        mock_logger.log_upload.assert_called_once()
        call_kwargs = mock_logger.log_upload.call_args.kwargs
        assert call_kwargs["session_id"] == "sess-123"
        assert call_kwargs["filename"] == "audit-label"
        assert call_kwargs["file_type"] == ".txt"

    def test_empty_sanitized_label_raises(self, vector_store):
        """A label that sanitizes to empty (e.g. all symbols) raises ValueError."""
        with pytest.raises(ValueError, match="empty collection name"):
            ingest_text_into_store(text="Some text.", label="@@@", store=vector_store)

    def test_audit_logger_skipped_without_session(self, vector_store):
        """Audit logger is not called when session_id is absent."""
        mock_logger = MagicMock()
        ingest_text_into_store(
            text="No session.",
            label="no-session-label",
            store=vector_store,
            audit_logger=mock_logger,
        )
        mock_logger.log_upload.assert_not_called()


# ---------------------------------------------------------------------------
# API integration tests: POST /upload-text
# ---------------------------------------------------------------------------


class TestUploadTextEndpoint:
    def test_success_returns_200(self, autofill_client, valid_token):
        """Valid text with auth → 200 and status=='success'."""
        resp = autofill_client.post(
            "/upload-text",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"text": "Some useful context for the survey.", "label": "My context"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["filename"] == "My context"
        assert data["size_bytes"] > 0
        assert "upload_timestamp" in data
        assert "session_id" in data

    def test_default_label_applied(self, autofill_client, valid_token):
        """Omitting label → filename defaults to 'pasted text'."""
        resp = autofill_client.post(
            "/upload-text",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"text": "Context without label."},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "pasted text"

    def test_empty_text_returns_422(self, autofill_client, valid_token):
        """Empty string → 422 Unprocessable Entity (Pydantic min_length=1)."""
        resp = autofill_client.post(
            "/upload-text",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"text": ""},
        )
        assert resp.status_code == 422

    def test_whitespace_only_returns_400(self, autofill_client, valid_token):
        """Whitespace-only text → 400 Bad Request."""
        resp = autofill_client.post(
            "/upload-text",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"text": "   \n\t  "},
        )
        assert resp.status_code == 400

    def test_whitespace_only_label_defaults_to_pasted_text(self, autofill_client, valid_token):
        """Whitespace-only label is stripped and defaults to 'pasted text'."""
        resp = autofill_client.post(
            "/upload-text",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"text": "Some useful context.", "label": "   "},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "pasted text"

    def test_unauthenticated_returns_401(self, autofill_client):
        """Missing auth token → 401 Unauthorized."""
        resp = autofill_client.post(
            "/upload-text",
            json={"text": "Some text."},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# UI router tests: documents page text snippet
# ---------------------------------------------------------------------------

BASE = "http://localhost:8801"
SESSION_ID = "session-text-test"
TOKEN_COOKIE = {"autofill_token": "test-jwt-token"}


class TestDocumentsPageTextSnippet:
    @respx.mock
    def test_textarea_present_on_documents_page(self):
        """Documents page renders the paste-text card with textarea and label inputs."""
        respx.get(f"{BASE}/session/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": SESSION_ID,
                    "user_id": "user-test",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2026-01-02T00:00:00Z",
                    "remaining_hours": 24.0,
                    "is_expired": False,
                    "document_count": 0,
                    "documents": [],
                    "isolation_scope": "user",
                    "last_upload_at": None,
                    "web_ingest_enabled": False,
                    "web_consent": False,
                },
            )
        )
        client = TestClient(ui_app, follow_redirects=False)
        resp = client.get(f"/session/{SESSION_ID}/documents", cookies=TOKEN_COOKIE)
        assert resp.status_code == 200
        assert 'id="text-snippet"' in resp.text
        assert 'id="text-label"' in resp.text
        assert 'id="text-card-form"' in resp.text
