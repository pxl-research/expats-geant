"""Tests for SessionManager."""

import json
import time
from datetime import timedelta

import pytest

from m_shared.session import SessionManager


class TestSessionManagerBasics:
    """Tests for basic SessionManager operations."""

    def test_init_creates_base_path(self, tmp_path):
        """Test that SessionManager creates base directory."""
        base = tmp_path / "sessions"
        _manager = SessionManager(base_path=str(base))

        assert base.exists()
        assert base.is_dir()

    def test_hash_token_stable(self, tmp_path):
        """Test that same token produces same session_id."""
        manager = SessionManager(base_path=str(tmp_path))

        token = "test_jwt_token_abc123"
        hash1 = manager._hash_token(token)
        hash2 = manager._hash_token(token)

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_token_different_for_different_tokens(self, tmp_path):
        """Test that different tokens produce different session_ids."""
        manager = SessionManager(base_path=str(tmp_path))

        hash1 = manager._hash_token("token1")
        hash2 = manager._hash_token("token2")

        assert hash1 != hash2


class TestSessionCreation:
    """Tests for session creation."""

    def test_create_session_basic(self, tmp_path):
        """Test basic session creation."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="test_token", ttl_hours=24)

        assert session.session_id is not None
        assert session.user_id == "user_123"
        assert session.isolation_scope == "user"
        assert not session.is_expired()

    def test_create_session_creates_folder_structure(self, tmp_path):
        """Test that session creation creates proper folder structure."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="test_token")

        session_path = tmp_path / session.session_id
        assert session_path.exists()
        assert (session_path / "metadata.json").exists()
        assert (session_path / "chroma_store").exists()
        assert (session_path / "uploads").exists()

    def test_create_session_saves_metadata(self, tmp_path):
        """Test that session metadata is saved correctly."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(
            user_id="user_456", jwt_token="another_token", ttl_hours=48
        )

        metadata_path = tmp_path / session.session_id / "metadata.json"
        with open(metadata_path) as f:
            data = json.load(f)

        assert data["user_id"] == "user_456"
        assert data["session_id"] == session.session_id
        assert data["metadata"]["ttl_hours"] == 48

    def test_create_session_with_existing_valid_returns_existing(self, tmp_path):
        """Test that creating session with same token returns existing if valid."""
        manager = SessionManager(base_path=str(tmp_path))

        token = "test_token"
        session1 = manager.create_session(user_id="user_123", jwt_token=token)
        session2 = manager.create_session(user_id="user_123", jwt_token=token)

        assert session1.session_id == session2.session_id

    def test_create_session_custom_ttl(self, tmp_path):
        """Test session creation with custom TTL."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_789", jwt_token="token_789", ttl_hours=1)

        expected_expiry = session.created_at + timedelta(hours=1)
        # Allow small time difference
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 2


class TestSessionRetrieval:
    """Tests for session retrieval."""

    def test_get_session_existing(self, tmp_path):
        """Test retrieving an existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        created = manager.create_session(user_id="user_123", jwt_token="token_abc")
        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.user_id == created.user_id

    def test_get_session_nonexistent(self, tmp_path):
        """Test retrieving nonexistent session returns None."""
        manager = SessionManager(base_path=str(tmp_path))

        result = manager.get_session("nonexistent_id")

        assert result is None

    def test_get_session_expired_returns_none(self, tmp_path):
        """Test that expired session returns None."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create session with very short TTL
        session = manager.create_session(
            user_id="user_123",
            jwt_token="token_short",
            ttl_hours=0.0001,  # ~0.36 seconds
        )

        # Wait for expiration
        time.sleep(1)

        retrieved = manager.get_session(session.session_id)
        assert retrieved is None


class TestVectorStore:
    """Tests for vector store access."""

    def test_get_vector_store_success(self, tmp_path):
        """Test getting vector store for existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_xyz")
        store = manager.get_vector_store(session.session_id)

        assert store is not None
        assert hasattr(store, "add_document")
        assert hasattr(store, "query")

    def test_get_vector_store_nonexistent_raises(self, tmp_path):
        """Test that getting store for nonexistent session raises error."""
        manager = SessionManager(base_path=str(tmp_path))

        with pytest.raises(FileNotFoundError):
            manager.get_vector_store("nonexistent_session")

    def test_get_documents_path(self, tmp_path):
        """Test getting documents path for session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_doc")
        docs_path = manager.get_documents_path(session.session_id)

        assert docs_path.exists()
        assert docs_path.is_dir()
        assert docs_path.name == "uploads"


class TestSessionDeletion:
    """Tests for session deletion."""

    def test_delete_session_success(self, tmp_path):
        """Test successful session deletion."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_del")
        assert manager.delete_session(session.session_id)

        # Verify session is gone
        session_path = tmp_path / session.session_id
        assert not session_path.exists()

    def test_delete_session_nonexistent(self, tmp_path):
        """Test deleting nonexistent session returns False."""
        manager = SessionManager(base_path=str(tmp_path))

        result = manager.delete_session("nonexistent_id")
        assert result is False

    def test_delete_session_removes_all_data(self, tmp_path):
        """Test that deletion removes all session data."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_data")

        # Add some files
        docs_path = manager.get_documents_path(session.session_id)
        (docs_path / "test.txt").write_text("test content")

        # Delete session
        manager.delete_session(session.session_id)

        # Verify everything is gone
        assert not docs_path.exists()
        assert not (tmp_path / session.session_id).exists()


class TestSessionListing:
    """Tests for listing sessions."""

    def test_list_sessions_empty(self, tmp_path):
        """Test listing sessions when none exist."""
        manager = SessionManager(base_path=str(tmp_path))

        sessions = manager.list_sessions()
        assert sessions == []

    def test_list_sessions_multiple(self, tmp_path):
        """Test listing multiple sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        s1 = manager.create_session(user_id="user_1", jwt_token="token_1")
        s2 = manager.create_session(user_id="user_2", jwt_token="token_2")
        s3 = manager.create_session(user_id="user_3", jwt_token="token_3")

        sessions = manager.list_sessions()
        assert len(sessions) == 3

        session_ids = {s.session_id for s in sessions}
        assert s1.session_id in session_ids
        assert s2.session_id in session_ids
        assert s3.session_id in session_ids

    def test_list_sessions_excludes_expired_by_default(self, tmp_path):
        """Test that expired sessions are excluded by default."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create one valid and one expired session
        valid = manager.create_session(user_id="user_1", jwt_token="token_1", ttl_hours=24)
        expired = manager.create_session(user_id="user_2", jwt_token="token_2", ttl_hours=0.0001)

        time.sleep(1)

        sessions = manager.list_sessions(include_expired=False)
        session_ids = [s.session_id for s in sessions]

        assert valid.session_id in session_ids
        assert expired.session_id not in session_ids

    def test_list_sessions_includes_expired_when_requested(self, tmp_path):
        """Test that expired sessions are included when requested."""
        manager = SessionManager(base_path=str(tmp_path))

        valid = manager.create_session(user_id="user_1", jwt_token="token_1", ttl_hours=24)
        expired = manager.create_session(user_id="user_2", jwt_token="token_2", ttl_hours=0.0001)

        time.sleep(1)

        sessions = manager.list_sessions(include_expired=True)
        session_ids = [s.session_id for s in sessions]

        assert valid.session_id in session_ids
        assert expired.session_id in session_ids


class TestCleanup:
    """Tests for cleanup operations."""

    def test_cleanup_expired_sessions_basic(self, tmp_path):
        """Test basic cleanup of expired sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create expired session
        expired = manager.create_session(user_id="user_1", jwt_token="token_exp", ttl_hours=0.0001)
        time.sleep(1)

        # Create valid session
        valid = manager.create_session(user_id="user_2", jwt_token="token_val", ttl_hours=24)

        deleted = manager.cleanup_expired_sessions()

        assert len(deleted) == 1
        assert expired.session_id in deleted
        assert not (tmp_path / expired.session_id).exists()
        assert (tmp_path / valid.session_id).exists()

    def test_cleanup_multiple_expired(self, tmp_path):
        """Test cleanup removes all expired sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create multiple expired sessions
        exp1 = manager.create_session(user_id="user_1", jwt_token="token_1", ttl_hours=0.0001)
        exp2 = manager.create_session(user_id="user_2", jwt_token="token_2", ttl_hours=0.0001)
        exp3 = manager.create_session(user_id="user_3", jwt_token="token_3", ttl_hours=0.0001)

        time.sleep(1)

        deleted = manager.cleanup_expired_sessions()

        assert len(deleted) == 3
        assert exp1.session_id in deleted
        assert exp2.session_id in deleted
        assert exp3.session_id in deleted

    def test_cleanup_no_expired_returns_empty(self, tmp_path):
        """Test cleanup with no expired sessions returns empty list."""
        manager = SessionManager(base_path=str(tmp_path))

        manager.create_session(user_id="user_1", jwt_token="token_1", ttl_hours=24)
        manager.create_session(user_id="user_2", jwt_token="token_2", ttl_hours=24)

        deleted = manager.cleanup_expired_sessions()

        assert deleted == []


class TestSessionStats:
    """Tests for session statistics."""

    def test_get_session_stats_existing(self, tmp_path):
        """Test getting statistics for existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_stats", ttl_hours=24)
        stats = manager.get_session_stats(session.session_id)

        assert stats is not None
        assert stats["session_id"] == session.session_id
        assert stats["user_id"] == "user_123"
        assert stats["remaining_hours"] > 23
        assert stats["remaining_hours"] <= 24
        assert stats["is_expired"] is False
        assert stats["document_count"] == 0

    def test_get_session_stats_nonexistent(self, tmp_path):
        """Test getting stats for nonexistent session returns None."""
        manager = SessionManager(base_path=str(tmp_path))

        stats = manager.get_session_stats("nonexistent_id")
        assert stats is None

    def test_get_session_stats_with_documents(self, tmp_path):
        """Test session stats include document count."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", jwt_token="token_docs")
        docs_path = manager.get_documents_path(session.session_id)

        # Add some files
        (docs_path / "doc1.txt").write_text("content1")
        (docs_path / "doc2.txt").write_text("content2")

        stats = manager.get_session_stats(session.session_id)

        assert stats["document_count"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
