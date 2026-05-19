"""Integration tests for session isolation with vector stores."""

import hashlib
from pathlib import Path

import pytest

from cue_api.ingest import ingest_files_into_store
from m_shared.session import SessionManager

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


def _user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class TestSessionIsolation:
    """Tests for session-based isolation."""

    def test_different_sessions_have_isolated_stores(self, tmp_path):
        """Test that different sessions cannot see each other's data."""
        manager = SessionManager(base_path=str(tmp_path))

        session1 = manager.create_session(user_id="user_1")
        session2 = manager.create_session(user_id="user_2")

        store1 = manager.get_vector_store(session1.session_id)
        store2 = manager.get_vector_store(session2.session_id)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        added1 = ingest_files_into_store(file_paths=[file_path], store=store1, max_chunk_size=512)

        assert len(added1) == 1

        results1 = store1.query(query_text="document", n_results=5)
        assert len(results1) > 0

        results2 = store2.query(query_text="document", n_results=5)
        assert len(results2) == 0

    def test_explicit_session_id_resumes(self, tmp_path):
        """Test that same explicit_session_id maps to same session."""
        manager = SessionManager(base_path=str(tmp_path))

        session1 = manager.create_session(user_id="user_1", explicit_session_id="fixed_123")
        session2 = manager.create_session(user_id="user_1", explicit_session_id="fixed_123")

        assert session1.session_id == session2.session_id

    def test_multiple_documents_in_session(self, tmp_path):
        """Test adding multiple documents to a session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_1")
        store = manager.get_vector_store(session.session_id)

        file_paths = [
            str(TEST_DATA_DIR / "sample.txt"),
            str(TEST_DATA_DIR / "sample_markdown.md"),
            str(TEST_DATA_DIR / "long_text.txt"),
        ]

        added = ingest_files_into_store(file_paths=file_paths, store=store, max_chunk_size=512)

        assert len(added) == 3

        documents = store.list_documents()
        assert len(documents) == 3

    def test_session_deletion_removes_vector_store(self, tmp_path):
        """Test that deleting session removes all vector store data."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_1")
        store = manager.get_vector_store(session.session_id)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        results = store.query(query_text="document", n_results=5)
        assert len(results) > 0

        manager.delete_session(session.session_id)

        session_path = tmp_path / _user_hash("user_1") / session.session_id
        assert not session_path.exists()

    def test_concurrent_sessions_no_interference(self, tmp_path):
        """Test that concurrent sessions don't interfere with each other."""
        manager = SessionManager(base_path=str(tmp_path))

        sessions = []
        stores = []
        for i in range(5):
            session = manager.create_session(user_id=f"user_{i}")
            store = manager.get_vector_store(session.session_id)
            sessions.append(session)
            stores.append(store)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        for store in stores:
            added = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)
            assert len(added) == 1

        for store in stores:
            documents = store.list_documents()
            assert len(documents) == 1

            results = store.query(query_text="document", n_results=5)
            assert len(results) > 0


class TestSessionCleanupIntegration:
    """Integration tests for session cleanup."""

    def test_cleanup_removes_vector_store_data(self, tmp_path):
        """Test that cleanup removes all vector store data for expired sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        import time

        session = manager.create_session(user_id="user_exp", ttl_hours=0.0001)
        store = manager.get_vector_store(session.session_id)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        session_path = tmp_path / _user_hash("user_exp") / session.session_id
        assert session_path.exists()
        chroma_dir = session.metadata.get("chroma_dir", "chroma_store")
        assert (session_path / chroma_dir).exists()

        time.sleep(1)

        deleted = manager.cleanup_expired_sessions()

        assert session.session_id in deleted
        assert not session_path.exists()

    def test_cleanup_preserves_valid_sessions(self, tmp_path):
        """Test that cleanup doesn't affect valid sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        import time

        expired = manager.create_session(user_id="user_exp", ttl_hours=0.0001)
        valid = manager.create_session(user_id="user_val", ttl_hours=24)

        file_path = str(TEST_DATA_DIR / "sample.txt")

        store_exp = manager.get_vector_store(expired.session_id)
        ingest_files_into_store(file_paths=[file_path], store=store_exp, max_chunk_size=512)

        store_val = manager.get_vector_store(valid.session_id)
        ingest_files_into_store(file_paths=[file_path], store=store_val, max_chunk_size=512)

        time.sleep(1)

        deleted = manager.cleanup_expired_sessions()

        assert expired.session_id in deleted
        assert valid.session_id not in deleted

        valid_path = tmp_path / _user_hash("user_val") / valid.session_id
        assert valid_path.exists()
        results = store_val.query(query_text="document", n_results=5)
        assert len(results) > 0


class TestSessionResumption:
    """Tests for resuming existing sessions."""

    def test_resume_session_with_explicit_id(self, tmp_path):
        """Test that same explicit_session_id resumes existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        session1 = manager.create_session(user_id="user_1", explicit_session_id="resume_123")
        store1 = manager.get_vector_store(session1.session_id)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        added1 = ingest_files_into_store(file_paths=[file_path], store=store1, max_chunk_size=512)
        assert len(added1) == 1

        session2 = manager.create_session(user_id="user_1", explicit_session_id="resume_123")
        assert session2.session_id == session1.session_id

        store2 = manager.get_vector_store(session2.session_id)
        documents = store2.list_documents()
        assert len(documents) == 1

        results = store2.query(query_text="document", n_results=5)
        assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
