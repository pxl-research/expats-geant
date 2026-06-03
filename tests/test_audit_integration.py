"""Integration tests for audit logging flow."""

import tempfile
from pathlib import Path

import pytest

from cue_api.ingest import ingest_files_into_store
from m_shared.session import SessionManager
from m_shared.utils import AuditEventType, AuditLogger


class TestAuditIntegration:
    """Integration tests for complete audit flow."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def session_manager(self, temp_dir):
        """Create session manager."""
        return SessionManager(base_path=temp_dir)

    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create audit logger."""
        return AuditLogger(base_path=temp_dir)

    @pytest.fixture
    def session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            user_id="test_user",
            ttl_hours=24,
            terms_version="1.0",
            privacy_version="1.0",
        )

    @pytest.fixture
    def test_documents(self, tmp_path):
        """Create test documents."""
        doc1 = tmp_path / "test1.txt"
        doc1.write_text("This is a test document about software engineering.")

        doc2 = tmp_path / "test2.txt"
        doc2.write_text("This document contains information about Python programming.")

        return [str(doc1), str(doc2)]

    def test_full_audit_flow(self, session_manager, audit_logger, session, test_documents):
        """Test complete audit flow: upload -> suggest -> report."""
        session_id = session.session_id

        # Step 1: Upload documents (with audit logging)
        store = session_manager.get_vector_store(session_id)
        added = ingest_files_into_store(
            file_paths=test_documents,
            store=store,
            max_chunk_size=512,
            session_id=session_id,
            user_id="test_user",
            audit_logger=audit_logger,
        )

        assert len(added) == 2

        # Verify upload logs
        entries = audit_logger.get_entries(session_id)
        upload_entries = [e for e in entries if e.event_type == AuditEventType.UPLOAD]
        assert len(upload_entries) == 2

        # Step 2: Simulate suggestion-time audit logging
        # Previously this test invoked pipeline.suggest_answer() which exercised
        # the (now-removed) single-question RAG path. We log the same audit
        # entry directly — the assertion is on the audit pipeline, not on the
        # LLM call.
        audit_logger.log_suggestion(
            session_id=session_id,
            question="What is mentioned in the documents?",
            suggested_answer="Some suggested answer",
            sources_used=["test_doc.txt"],
            model="openrouter/anthropic/claude-3-sonnet",
            user_id="test_user",
        )
        suggest_entries = [
            e
            for e in audit_logger.get_entries(session_id)
            if e.event_type == AuditEventType.SUGGEST
        ]
        assert len(suggest_entries) == 1

        # Step 3: Simulate user edit
        audit_logger.log_edit(
            session_id=session_id,
            original_suggestion="Original answer",
            edited_version="Edited answer",
            question="Test question",
            user_id="test_user",
        )

        # Step 4: Generate audit report
        report = audit_logger.generate_report(
            session_id=session_id, user_id="test_user", created_at=session.created_at, ended_at=None
        )

        assert report.session_id == session_id
        assert report.user_id == "test_user"
        assert report.summary["documents_uploaded"] == 2
        assert report.summary["suggestions_edited"] >= 1
        assert report.consent is not None
        assert report.consent.terms_version == "1.0"

        # Verify all log types present
        all_entries = audit_logger.get_entries(session_id)
        event_types = {e.event_type for e in all_entries}
        assert AuditEventType.SESSION_START in event_types
        assert AuditEventType.CONSENT_ACCEPTED in event_types
        assert AuditEventType.UPLOAD in event_types
        assert AuditEventType.EDIT_SUGGESTION in event_types

    def test_session_lifecycle_audit(self, session_manager, audit_logger, session):
        """Test session lifecycle events are audited."""
        session_id = session.session_id

        # Session start and consent should be logged on creation
        entries = audit_logger.get_entries(session_id)
        assert len(entries) == 2  # SESSION_START + CONSENT_ACCEPTED

        start_entry = entries[0]
        assert start_entry.event_type == AuditEventType.SESSION_START
        assert start_entry.user_id == "test_user"

        consent_entry = entries[1]
        assert consent_entry.event_type == AuditEventType.CONSENT_ACCEPTED

        # Delete session (should log SESSION_END)
        session_manager.delete_session(session_id, reason="test_cleanup")

        # Note: After deletion, we can't retrieve entries
        # This is expected behavior - audit logs are deleted with session

    def test_audit_report_formats(self, audit_logger, session_manager, session, test_documents):
        """Test different audit report formats."""
        session_id = session.session_id

        # Add some activity
        store = session_manager.get_vector_store(session_id)
        ingest_files_into_store(
            file_paths=[test_documents[0]],
            store=store,
            session_id=session_id,
            user_id="test_user",
            audit_logger=audit_logger,
        )

        # Generate report
        report = audit_logger.generate_report(session_id=session_id, user_id="test_user")

        # Test JSON format
        json_report = audit_logger.format_report(report, format_type="json")
        assert "session_id" in json_report
        assert session_id in json_report

        # Test plaintext format
        text_report = audit_logger.format_report(report, format_type="plaintext")
        assert "AUDIT REPORT" in text_report
        assert "SUMMARY" in text_report
        assert "ACTIVITY LOG" in text_report
        assert "SESSION_START" in text_report
        assert "UPLOAD" in text_report

        # Test markdown format
        from cue_api.routes.audit import _format_audit_markdown

        md_report = _format_audit_markdown(report, session_id)
        assert "# Audit Report" in md_report
        assert session_id in md_report
        assert "## Documents Uploaded" in md_report
        assert "## Summary" in md_report

    def test_retention_and_cleanup(self, session_manager, audit_logger, session):
        """Test retention policy enforcement."""
        session_id = session.session_id

        # Mark report as claimed
        audit_logger.mark_claimed(session_id)
        assert audit_logger.is_claimed(session_id)

        # Cleanup shouldn't affect claimed reports (within retention period)
        # Note: _cleanup_old_reports uses file modification time, so we can't
        # easily test the actual cleanup without time manipulation

        # Just verify the mechanism exists
        cleaned = session_manager._cleanup_old_reports(retention_years=1)
        # Should be empty since report is recent
        assert session_id not in cleaned

    def test_concurrent_session_isolation(self, session_manager, audit_logger, test_documents):
        """Test audit logs are isolated across concurrent sessions."""
        # Create two sessions
        session1 = session_manager.create_session(user_id="user1", ttl_hours=24)

        session2 = session_manager.create_session(user_id="user2", ttl_hours=24)

        # Upload different documents to each
        store1 = session_manager.get_vector_store(session1.session_id)
        ingest_files_into_store(
            file_paths=[test_documents[0]],
            store=store1,
            session_id=session1.session_id,
            user_id="user1",
            audit_logger=audit_logger,
        )

        store2 = session_manager.get_vector_store(session2.session_id)
        ingest_files_into_store(
            file_paths=[test_documents[1]],
            store=store2,
            session_id=session2.session_id,
            user_id="user2",
            audit_logger=audit_logger,
        )

        # Verify isolation
        entries1 = audit_logger.get_entries(session1.session_id)
        entries2 = audit_logger.get_entries(session2.session_id)

        # Each should have SESSION_START + CONSENT_ACCEPTED + 1 UPLOAD
        assert len(entries1) == 3
        assert len(entries2) == 3

        # Verify correct user IDs
        assert all(e.user_id == "user1" or e.user_id is None for e in entries1)
        assert all(e.user_id == "user2" or e.user_id is None for e in entries2)

        # Verify correct filenames
        upload1 = [e for e in entries1 if e.event_type == AuditEventType.UPLOAD][0]
        upload2 = [e for e in entries2 if e.event_type == AuditEventType.UPLOAD][0]

        assert upload1.details["filename"] == "test1.txt"
        assert upload2.details["filename"] == "test2.txt"

    def test_audit_with_session_expiry(self, session_manager, audit_logger):
        """Test audit logs are preserved when session expires."""
        # Create session with very short TTL
        session = session_manager.create_session(
            user_id="test_user",
            ttl_hours=0,  # Expires immediately
        )

        session_id = session.session_id

        # Add some audit entries
        audit_logger.log_upload(
            session_id=session_id,
            filename="test.pdf",
            file_size=1000,
            file_type=".pdf",
            user_id="test_user",
        )

        # Generate report
        report = audit_logger.generate_report(session_id=session_id, user_id="test_user")

        assert report.summary["documents_uploaded"] == 1

        # Cleanup expired sessions
        deleted = session_manager.cleanup_expired_sessions()

        # Session should be in deleted list
        assert session_id in deleted


class TestAuditWithRealDocuments:
    """Integration tests using actual test data files."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_audit_with_test_data(self, temp_dir):
        """Test audit logging with real test documents."""
        test_data_path = Path(__file__).parent / "test_data" / "documents"
        if not test_data_path.exists():
            pytest.skip("Test data not available")

        # Find test documents
        test_docs = list(test_data_path.glob("*.txt"))
        if not test_docs:
            pytest.skip("No .txt test documents available")

        session_manager = SessionManager(base_path=temp_dir)
        audit_logger = AuditLogger(base_path=temp_dir)

        session = session_manager.create_session(user_id="test_user")

        # Ingest documents
        store = session_manager.get_vector_store(session.session_id)
        added = ingest_files_into_store(
            file_paths=[str(doc) for doc in test_docs[:2]],  # Use first 2 docs
            store=store,
            session_id=session.session_id,
            user_id="test_user",
            audit_logger=audit_logger,
        )

        # Generate report
        report = audit_logger.generate_report(session_id=session.session_id, user_id="test_user")

        assert report.summary["documents_uploaded"] == len(added)
        assert len(report.log_entries) >= 2  # At least SESSION_START + CONSENT + uploads
