"""Tests for SessionManager."""

import hashlib
import json
import time
from datetime import timedelta

import pytest

from m_shared.session import SessionManager


def _user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class TestSessionManagerBasics:
    """Tests for basic SessionManager operations."""

    def test_init_creates_base_path(self, tmp_path):
        """Test that SessionManager creates base directory."""
        base = tmp_path / "sessions"
        _manager = SessionManager(base_path=str(base))

        assert base.exists()
        assert base.is_dir()

    def test_hash_user_id_stable(self, tmp_path):
        """Test that same user_id produces same hash."""
        manager = SessionManager(base_path=str(tmp_path))

        hash1 = manager._hash_user_id("user_123")
        hash2 = manager._hash_user_id("user_123")

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_hash_user_id_different_for_different_users(self, tmp_path):
        """Test that different user_ids produce different hashes."""
        manager = SessionManager(base_path=str(tmp_path))

        hash1 = manager._hash_user_id("user_1")
        hash2 = manager._hash_user_id("user_2")

        assert hash1 != hash2

    def test_ensure_user_directory(self, tmp_path):
        """Test that ensure_user_directory creates the user folder."""
        manager = SessionManager(base_path=str(tmp_path))

        user_path = manager.ensure_user_directory("user_123")

        assert user_path.exists()
        assert user_path.is_dir()
        assert user_path == tmp_path / _user_hash("user_123")


class TestSessionCreation:
    """Tests for session creation."""

    def test_create_session_basic(self, tmp_path):
        """Test basic session creation."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", ttl_hours=24)

        assert session.session_id is not None
        assert session.user_id == "user_123"
        assert session.isolation_scope == "user"
        assert not session.is_expired()

    def test_create_session_creates_folder_structure(self, tmp_path):
        """Test that session creation creates proper nested folder structure."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123")

        session_path = tmp_path / _user_hash("user_123") / session.session_id
        assert session_path.exists()
        assert (session_path / "metadata.json").exists()
        chroma_dir = session.metadata.get("chroma_dir", "chroma_store")
        assert (session_path / chroma_dir).exists()
        assert (session_path / "uploads").exists()

    def test_create_session_saves_metadata(self, tmp_path):
        """Test that session metadata is saved correctly."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_456", ttl_hours=48)

        session_path = tmp_path / _user_hash("user_456") / session.session_id
        metadata_path = session_path / "metadata.json"
        with open(metadata_path) as f:
            data = json.load(f)

        assert data["user_id"] == "user_456"
        assert data["session_id"] == session.session_id
        assert data["metadata"]["ttl_hours"] == 48

    def test_create_session_with_explicit_id_returns_existing(self, tmp_path):
        """Test that creating session with same explicit_session_id returns existing if valid."""
        manager = SessionManager(base_path=str(tmp_path))

        session1 = manager.create_session(user_id="user_123", explicit_session_id="fixed_id_123")
        session2 = manager.create_session(user_id="user_123", explicit_session_id="fixed_id_123")

        assert session1.session_id == session2.session_id

    def test_create_session_custom_ttl(self, tmp_path):
        """Test session creation with custom TTL."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_789", ttl_hours=1)

        expected_expiry = session.created_at + timedelta(hours=1)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 2


class TestSessionRetrieval:
    """Tests for session retrieval."""

    def test_get_session_existing(self, tmp_path):
        """Test retrieving an existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        created = manager.create_session(
            user_id="user_123",
        )
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

        session = manager.create_session(
            user_id="user_123",
        )
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

        session = manager.create_session(
            user_id="user_123",
        )
        docs_path = manager.get_documents_path(session.session_id)

        assert docs_path.exists()
        assert docs_path.is_dir()
        assert docs_path.name == "uploads"


class TestSessionDeletion:
    """Tests for session deletion."""

    def test_delete_session_success(self, tmp_path):
        """Test successful session deletion."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123")
        assert manager.delete_session(session.session_id)

        session_path = tmp_path / _user_hash("user_123") / session.session_id
        assert not session_path.exists()

    def test_delete_session_nonexistent(self, tmp_path):
        """Test deleting nonexistent session returns False."""
        manager = SessionManager(base_path=str(tmp_path))

        result = manager.delete_session("nonexistent_id")
        assert result is False

    def test_delete_session_removes_all_data(self, tmp_path):
        """Test that deletion removes all session data."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123")

        docs_path = manager.get_documents_path(session.session_id)
        (docs_path / "test.txt").write_text("test content")

        manager.delete_session(session.session_id)

        assert not docs_path.exists()
        session_path = tmp_path / _user_hash("user_123") / session.session_id
        assert not session_path.exists()

    def test_delete_last_session_removes_user_dir(self, tmp_path):
        """Test that deleting the last session also removes the empty user directory."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123")
        user_dir = tmp_path / _user_hash("user_123")
        assert user_dir.exists()

        manager.delete_session(session.session_id)
        assert not user_dir.exists()

    def test_delete_user_data(self, tmp_path):
        """Test RTBF: delete all user data at once."""
        manager = SessionManager(base_path=str(tmp_path))

        manager.create_session(user_id="user_123")
        manager.create_session(user_id="user_123")

        assert manager.delete_user_data("user_123")
        assert not (tmp_path / _user_hash("user_123")).exists()
        assert manager.list_sessions_for_user("user_123") == []

    def test_delete_user_data_nonexistent(self, tmp_path):
        """Test deleting nonexistent user returns False."""
        manager = SessionManager(base_path=str(tmp_path))
        assert manager.delete_user_data("nonexistent") is False


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

        s1 = manager.create_session(user_id="user_1")
        s2 = manager.create_session(user_id="user_2")
        s3 = manager.create_session(user_id="user_3")

        sessions = manager.list_sessions()
        assert len(sessions) == 3

        session_ids = {s.session_id for s in sessions}
        assert s1.session_id in session_ids
        assert s2.session_id in session_ids
        assert s3.session_id in session_ids

    def test_list_sessions_for_user(self, tmp_path):
        """Test listing sessions for a specific user."""
        manager = SessionManager(base_path=str(tmp_path))

        s1 = manager.create_session(user_id="user_1")
        s2 = manager.create_session(user_id="user_1")
        manager.create_session(user_id="user_2")

        sessions = manager.list_sessions_for_user("user_1")
        assert len(sessions) == 2
        session_ids = {s.session_id for s in sessions}
        assert s1.session_id in session_ids
        assert s2.session_id in session_ids

    def test_list_sessions_excludes_expired_by_default(self, tmp_path):
        """Test that expired sessions are excluded by default."""
        manager = SessionManager(base_path=str(tmp_path))

        valid = manager.create_session(user_id="user_1", ttl_hours=24)
        expired = manager.create_session(user_id="user_2", ttl_hours=0.0001)

        time.sleep(1)

        sessions = manager.list_sessions(include_expired=False)
        session_ids = [s.session_id for s in sessions]

        assert valid.session_id in session_ids
        assert expired.session_id not in session_ids

    def test_list_sessions_includes_expired_when_requested(self, tmp_path):
        """Test that expired sessions are included when requested."""
        manager = SessionManager(base_path=str(tmp_path))

        valid = manager.create_session(user_id="user_1", ttl_hours=24)
        expired = manager.create_session(user_id="user_2", ttl_hours=0.0001)

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

        expired = manager.create_session(user_id="user_1", ttl_hours=0.0001)
        time.sleep(1)

        valid = manager.create_session(user_id="user_2", ttl_hours=24)

        deleted = manager.cleanup_expired_sessions()

        assert len(deleted) == 1
        assert expired.session_id in deleted
        expired_path = tmp_path / _user_hash("user_1") / expired.session_id
        assert not expired_path.exists()
        valid_path = tmp_path / _user_hash("user_2") / valid.session_id
        assert valid_path.exists()

    def test_cleanup_multiple_expired(self, tmp_path):
        """Test cleanup removes all expired sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        exp1 = manager.create_session(user_id="user_1", ttl_hours=0.0001)
        exp2 = manager.create_session(user_id="user_2", ttl_hours=0.0001)
        exp3 = manager.create_session(user_id="user_3", ttl_hours=0.0001)

        time.sleep(1)

        deleted = manager.cleanup_expired_sessions()

        assert len(deleted) == 3
        assert exp1.session_id in deleted
        assert exp2.session_id in deleted
        assert exp3.session_id in deleted

    def test_cleanup_no_expired_returns_empty(self, tmp_path):
        """Test cleanup with no expired sessions returns empty list."""
        manager = SessionManager(base_path=str(tmp_path))

        manager.create_session(user_id="user_1", ttl_hours=24)
        manager.create_session(user_id="user_2", ttl_hours=24)

        deleted = manager.cleanup_expired_sessions()

        assert deleted == []

    def test_cleanup_prunes_empty_user_dirs(self, tmp_path):
        """Test that cleanup removes empty user directories."""
        manager = SessionManager(base_path=str(tmp_path))

        manager.create_session(user_id="user_1", ttl_hours=0.0001)
        time.sleep(1)

        manager.cleanup_expired_sessions()

        user_dir = tmp_path / _user_hash("user_1")
        assert not user_dir.exists()


class TestSessionStats:
    """Tests for session statistics."""

    def test_get_session_stats_existing(self, tmp_path):
        """Test getting statistics for existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_123", ttl_hours=24)
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
        """Test session stats reflect ingested document count from the vector store."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(
            user_id="user_123",
        )
        store = manager.get_vector_store(session.session_id)

        # Simulate ingested documents (raw files are deleted after ingestion)
        store.add_document("doc1", ["chunk1"], [{"source": "doc1"}])
        store.add_document("doc2", ["chunk2"], [{"source": "doc2"}])

        stats = manager.get_session_stats(session.session_id)

        assert stats["document_count"] == 2

    def test_last_upload_at_none_for_empty_session(self, tmp_path):
        manager = SessionManager(base_path=str(tmp_path))
        session = manager.create_session(user_id="user_123")
        stats = manager.get_session_stats(session.session_id)
        assert stats["last_upload_at"] is None

    def test_last_upload_at_reflects_ingested_chunk(self, tmp_path):
        from datetime import UTC, datetime

        manager = SessionManager(base_path=str(tmp_path))
        session = manager.create_session(user_id="user_123")
        store = manager.get_vector_store(session.session_id)
        ts = 1_700_000_000.5
        store.add_document("doc1", ["chunk1"], [{"source": "doc1", "ingested_at": ts}])

        stats = manager.get_session_stats(session.session_id)

        assert stats["last_upload_at"] == datetime.fromtimestamp(ts, tz=UTC).isoformat()

    def test_last_upload_at_returns_maximum_across_documents(self, tmp_path):
        from datetime import UTC, datetime

        manager = SessionManager(base_path=str(tmp_path))
        session = manager.create_session(user_id="user_123")
        store = manager.get_vector_store(session.session_id)
        earlier, later = 1_700_000_000.0, 1_700_001_000.0
        store.add_document("doc1", ["c1"], [{"source": "doc1", "ingested_at": earlier}])
        store.add_document("doc2", ["c2"], [{"source": "doc2", "ingested_at": later}])

        stats = manager.get_session_stats(session.session_id)

        assert stats["last_upload_at"] == datetime.fromtimestamp(later, tz=UTC).isoformat()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
