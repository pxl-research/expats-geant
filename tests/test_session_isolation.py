"""Integration tests for session isolation with vector stores."""

from pathlib import Path

import pytest

from m_autofill.ingest import ingest_files_into_store
from m_shared.session import SessionManager

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


class TestSessionIsolation:
    """Tests for session-based isolation."""

    def test_different_sessions_have_isolated_stores(self, tmp_path):
        """Test that different sessions cannot see each other's data."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create two sessions
        session1 = manager.create_session(user_id="user_1", jwt_token="token_1")
        session2 = manager.create_session(user_id="user_2", jwt_token="token_2")

        # Get vector stores
        store1 = manager.get_vector_store(session1.session_id)
        store2 = manager.get_vector_store(session2.session_id)

        # Add documents to session 1
        file_path = str(TEST_DATA_DIR / "sample.txt")
        added1 = ingest_files_into_store(file_paths=[file_path], store=store1, max_chunk_size=512)

        assert len(added1) == 1

        # Query session 1 - should find results
        results1 = store1.query(query_text="document", n_results=5)
        assert len(results1) > 0

        # Query session 2 - should find nothing
        results2 = store2.query(query_text="document", n_results=5)
        assert len(results2) == 0

    def test_same_token_same_session(self, tmp_path):
        """Test that same JWT token maps to same session."""
        manager = SessionManager(base_path=str(tmp_path))

        token = "consistent_token"
        session1 = manager.create_session(user_id="user_1", jwt_token=token)
        session2 = manager.create_session(user_id="user_1", jwt_token=token)

        assert session1.session_id == session2.session_id

    def test_multiple_documents_in_session(self, tmp_path):
        """Test adding multiple documents to a session."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_1", jwt_token="token_multi")
        store = manager.get_vector_store(session.session_id)

        # Add multiple documents
        file_paths = [
            str(TEST_DATA_DIR / "sample.txt"),
            str(TEST_DATA_DIR / "sample_markdown.md"),
            str(TEST_DATA_DIR / "long_text.txt"),
        ]

        added = ingest_files_into_store(file_paths=file_paths, store=store, max_chunk_size=512)

        assert len(added) == 3

        # List documents
        documents = store.list_documents()
        assert len(documents) == 3

    def test_session_deletion_removes_vector_store(self, tmp_path):
        """Test that deleting session removes all vector store data."""
        manager = SessionManager(base_path=str(tmp_path))

        session = manager.create_session(user_id="user_1", jwt_token="token_del")
        store = manager.get_vector_store(session.session_id)

        # Add document
        file_path = str(TEST_DATA_DIR / "sample.txt")
        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        # Verify data exists
        results = store.query(query_text="document", n_results=5)
        assert len(results) > 0

        # Delete session
        manager.delete_session(session.session_id)

        # Verify session folder is gone
        session_path = tmp_path / session.session_id
        assert not session_path.exists()

    def test_concurrent_sessions_no_interference(self, tmp_path):
        """Test that concurrent sessions don't interfere with each other."""
        manager = SessionManager(base_path=str(tmp_path))

        # Create multiple sessions simultaneously
        sessions = []
        stores = []
        for i in range(5):
            session = manager.create_session(user_id=f"user_{i}", jwt_token=f"token_{i}")
            store = manager.get_vector_store(session.session_id)
            sessions.append(session)
            stores.append(store)

        # Add documents to each session
        file_path = str(TEST_DATA_DIR / "sample.txt")
        for store in stores:
            added = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)
            assert len(added) == 1

        # Verify each session has exactly one document
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

        # Create expired session with data
        session = manager.create_session(
            user_id="user_exp", jwt_token="token_exp", ttl_hours=0.0001
        )
        store = manager.get_vector_store(session.session_id)

        # Add document
        file_path = str(TEST_DATA_DIR / "sample.txt")
        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        # Verify data exists
        session_path = tmp_path / session.session_id
        assert session_path.exists()
        assert (session_path / "chroma_store").exists()

        # Wait for expiration
        time.sleep(1)

        # Run cleanup
        deleted = manager.cleanup_expired_sessions()

        assert session.session_id in deleted
        assert not session_path.exists()

    def test_cleanup_preserves_valid_sessions(self, tmp_path):
        """Test that cleanup doesn't affect valid sessions."""
        manager = SessionManager(base_path=str(tmp_path))

        import time

        # Create one expired and one valid session
        expired = manager.create_session(
            user_id="user_exp", jwt_token="token_exp", ttl_hours=0.0001
        )
        valid = manager.create_session(user_id="user_val", jwt_token="token_val", ttl_hours=24)

        # Add data to both
        file_path = str(TEST_DATA_DIR / "sample.txt")

        store_exp = manager.get_vector_store(expired.session_id)
        ingest_files_into_store(file_paths=[file_path], store=store_exp, max_chunk_size=512)

        store_val = manager.get_vector_store(valid.session_id)
        ingest_files_into_store(file_paths=[file_path], store=store_val, max_chunk_size=512)

        # Wait for expiration
        time.sleep(1)

        # Run cleanup
        deleted = manager.cleanup_expired_sessions()

        assert expired.session_id in deleted
        assert valid.session_id not in deleted

        # Verify valid session still exists and works
        assert (tmp_path / valid.session_id).exists()
        results = store_val.query(query_text="document", n_results=5)
        assert len(results) > 0


class TestSessionResumption:
    """Tests for resuming existing sessions."""

    def test_resume_session_with_same_token(self, tmp_path):
        """Test that same token resumes existing session."""
        manager = SessionManager(base_path=str(tmp_path))

        token = "resumable_token"

        # Create session and add data
        session1 = manager.create_session(user_id="user_1", jwt_token=token)
        store1 = manager.get_vector_store(session1.session_id)

        file_path = str(TEST_DATA_DIR / "sample.txt")
        added1 = ingest_files_into_store(file_paths=[file_path], store=store1, max_chunk_size=512)
        assert len(added1) == 1

        # "Resume" session with same token
        session2 = manager.create_session(user_id="user_1", jwt_token=token)
        assert session2.session_id == session1.session_id

        # Get store and verify data is still there
        store2 = manager.get_vector_store(session2.session_id)
        documents = store2.list_documents()
        assert len(documents) == 1

        # Verify we can query the existing data
        results = store2.query(query_text="document", n_results=5)
        assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
