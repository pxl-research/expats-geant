"""Unit tests for audit logging functionality."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from m_shared.utils import (
    AuditEventType,
    AuditLogEntry,
    AuditLogger,
    AuditReport,
    Consent,
)


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""

    def test_create_upload_entry(self):
        """Test creating an upload audit log entry."""
        entry = AuditLogEntry(
            event_type=AuditEventType.UPLOAD,
            session_id="sess_123",
            user_id="user_456",
            details={"filename": "cv.pdf", "file_size": 50000, "file_type": ".pdf"},
        )

        assert entry.event_type == AuditEventType.UPLOAD
        assert entry.session_id == "sess_123"
        assert entry.user_id == "user_456"
        assert entry.details["filename"] == "cv.pdf"
        assert entry.details["file_size"] == 50000
        assert isinstance(entry.timestamp, datetime)

    def test_create_suggest_entry(self):
        """Test creating a suggestion audit log entry."""
        entry = AuditLogEntry(
            event_type=AuditEventType.SUGGEST,
            session_id="sess_123",
            details={
                "question": "What is my job title?",
                "suggested_answer": "Senior Developer",
                "sources_used": ["cv.pdf", "contract.pdf"],
                "model": "anthropic/claude-3-sonnet",
            },
        )

        assert entry.event_type == AuditEventType.SUGGEST
        assert entry.details["question"] == "What is my job title?"
        assert len(entry.details["sources_used"]) == 2

    def test_entry_serialization(self):
        """Test audit entry serializes to JSON correctly."""
        entry = AuditLogEntry(
            event_type=AuditEventType.UPLOAD,
            session_id="sess_123",
            details={"filename": "test.pdf"},
        )

        data = entry.model_dump(mode="json")

        assert data["event_type"] == "UPLOAD"
        assert data["session_id"] == "sess_123"
        assert "timestamp" in data


class TestConsent:
    """Tests for Consent model."""

    def test_create_consent(self):
        """Test creating a consent record."""
        consent = Consent(session_id="sess_123", terms_version="1.0", privacy_version="1.0")

        assert consent.session_id == "sess_123"
        assert consent.terms_version == "1.0"
        assert consent.privacy_version == "1.0"
        assert isinstance(consent.accepted_at, datetime)

    def test_consent_with_custom_timestamp(self):
        """Test consent with custom accepted_at timestamp."""
        custom_time = datetime(2026, 1, 1, 12, 0, 0)
        consent = Consent(
            session_id="sess_123",
            accepted_at=custom_time,
            terms_version="1.0",
            privacy_version="1.0",
        )

        assert consent.accepted_at == custom_time


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def logger(self, temp_dir):
        """Create an audit logger instance."""
        return AuditLogger(base_path=temp_dir)

    def test_logger_initialization(self, temp_dir):
        """Test audit logger initializes correctly."""
        logger = AuditLogger(base_path=temp_dir)
        assert logger.base_path == Path(temp_dir)

    def test_log_upload(self, logger, temp_dir):
        """Test logging a file upload."""
        logger.log_upload(
            session_id="sess_123",
            filename="cv.pdf",
            file_size=50000,
            file_type=".pdf",
            user_id="user_456",
        )

        # Check log file was created
        log_path = Path(temp_dir) / "sess_123" / "audit_log.json"
        assert log_path.exists()

        # Load and verify content
        entries = logger.get_entries("sess_123")
        assert len(entries) == 1
        assert entries[0].event_type == AuditEventType.UPLOAD
        assert entries[0].details["filename"] == "cv.pdf"
        assert entries[0].details["file_size"] == 50000

    def test_log_suggestion(self, logger):
        """Test logging a suggestion generation."""
        logger.log_suggestion(
            session_id="sess_123",
            question="What is my job title?",
            suggested_answer="Senior Developer",
            sources_used=["cv.pdf", "contract.pdf"],
            model="anthropic/claude-3-sonnet",
            user_id="user_456",
        )

        entries = logger.get_entries("sess_123")
        assert len(entries) == 1
        assert entries[0].event_type == AuditEventType.SUGGEST
        assert entries[0].details["question"] == "What is my job title?"
        assert len(entries[0].details["sources_used"]) == 2

    def test_log_suggestion_with_rewritten_query(self, logger):
        """Test logging a suggestion with rewritten query."""
        logger.log_suggestion(
            session_id="sess_123",
            question="Could you please describe your current employment status?",
            suggested_answer="Full-time researcher",
            sources_used=["contract.pdf"],
            model="anthropic/claude-3-sonnet",
            rewritten_query="employment status",
        )

        entries = logger.get_entries("sess_123")
        assert len(entries) == 1
        assert entries[0].details["rewritten_query"] == "employment status"

    def test_log_suggestion_without_rewritten_query(self, logger):
        """Test that rewritten_query is absent when not provided."""
        logger.log_suggestion(
            session_id="sess_123",
            question="Question?",
            suggested_answer="Answer",
            sources_used=[],
            model="test-model",
        )

        entries = logger.get_entries("sess_123")
        assert "rewritten_query" not in entries[0].details

    def test_log_edit(self, logger):
        """Test logging a user edit."""
        logger.log_edit(
            session_id="sess_123",
            original_suggestion="Senior Developer",
            edited_version="Senior Software Developer",
            question="What is my job title?",
            user_id="user_456",
        )

        entries = logger.get_entries("sess_123")
        assert len(entries) == 1
        assert entries[0].event_type == AuditEventType.EDIT_SUGGESTION
        assert entries[0].details["original_suggestion"] == "Senior Developer"
        assert entries[0].details["edited_version"] == "Senior Software Developer"

    def test_log_session_event(self, logger):
        """Test logging session lifecycle events."""
        logger.log_session_event(
            session_id="sess_123", event_type=AuditEventType.SESSION_START, user_id="user_456"
        )

        logger.log_session_event(
            session_id="sess_123",
            event_type=AuditEventType.SESSION_END,
            user_id="user_456",
            reason="user_logout",
        )

        entries = logger.get_entries("sess_123")
        assert len(entries) == 2
        assert entries[0].event_type == AuditEventType.SESSION_START
        assert entries[1].event_type == AuditEventType.SESSION_END
        assert entries[1].details["reason"] == "user_logout"

    def test_log_consent(self, logger):
        """Test logging consent acceptance."""
        consent = Consent(session_id="sess_123", terms_version="1.0", privacy_version="1.0")

        logger.log_consent(session_id="sess_123", consent=consent, user_id="user_456")

        entries = logger.get_entries("sess_123")
        assert len(entries) == 1
        assert entries[0].event_type == AuditEventType.CONSENT_ACCEPTED
        assert entries[0].details["terms_version"] == "1.0"
        assert entries[0].details["privacy_version"] == "1.0"

    def test_multiple_entries_chronological(self, logger):
        """Test multiple entries are stored in chronological order."""
        logger.log_upload(
            session_id="sess_123", filename="file1.pdf", file_size=1000, file_type=".pdf"
        )

        logger.log_upload(
            session_id="sess_123", filename="file2.pdf", file_size=2000, file_type=".pdf"
        )

        logger.log_suggestion(
            session_id="sess_123",
            question="Test question",
            suggested_answer="Test answer",
            sources_used=["file1.pdf"],
            model="test-model",
        )

        entries = logger.get_entries("sess_123")
        assert len(entries) == 3
        assert entries[0].details["filename"] == "file1.pdf"
        assert entries[1].details["filename"] == "file2.pdf"
        assert entries[2].event_type == AuditEventType.SUGGEST

        # Verify chronological order
        for i in range(len(entries) - 1):
            assert entries[i].timestamp <= entries[i + 1].timestamp

    def test_session_isolation(self, logger):
        """Test entries are isolated per session."""
        logger.log_upload(
            session_id="sess_123", filename="file1.pdf", file_size=1000, file_type=".pdf"
        )

        logger.log_upload(
            session_id="sess_456", filename="file2.pdf", file_size=2000, file_type=".pdf"
        )

        entries_123 = logger.get_entries("sess_123")
        entries_456 = logger.get_entries("sess_456")

        assert len(entries_123) == 1
        assert len(entries_456) == 1
        assert entries_123[0].details["filename"] == "file1.pdf"
        assert entries_456[0].details["filename"] == "file2.pdf"

    def test_get_entries_empty_session(self, logger):
        """Test getting entries for non-existent session returns empty list."""
        entries = logger.get_entries("nonexistent_session")
        assert entries == []

    def test_thread_safety(self, logger):
        """Test concurrent logging is thread-safe."""
        import threading

        def log_entries(session_id, count):
            for i in range(count):
                logger.log_upload(
                    session_id=session_id,
                    filename=f"file_{i}.pdf",
                    file_size=i * 1000,
                    file_type=".pdf",
                )

        threads = [threading.Thread(target=log_entries, args=("sess_123", 10)) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = logger.get_entries("sess_123")
        assert len(entries) == 50  # 5 threads * 10 entries each


class TestAuditReport:
    """Tests for AuditReport generation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def logger(self, temp_dir):
        """Create an audit logger instance."""
        return AuditLogger(base_path=temp_dir)

    def test_generate_report_empty_session(self, logger):
        """Test generating report for session with no entries."""
        report = logger.generate_report(session_id="sess_123", user_id="user_456")

        assert report.session_id == "sess_123"
        assert report.user_id == "user_456"
        assert len(report.log_entries) == 0
        assert report.summary["total_events"] == 0

    def test_generate_report_with_entries(self, logger):
        """Test generating report with multiple entries."""
        # Add various entries
        logger.log_upload(
            session_id="sess_123", filename="cv.pdf", file_size=50000, file_type=".pdf"
        )

        logger.log_upload(
            session_id="sess_123", filename="contract.pdf", file_size=30000, file_type=".pdf"
        )

        logger.log_suggestion(
            session_id="sess_123",
            question="What is my title?",
            suggested_answer="Developer",
            sources_used=["cv.pdf"],
            model="test-model",
        )

        logger.log_edit(
            session_id="sess_123",
            original_suggestion="Developer",
            edited_version="Senior Developer",
        )

        report = logger.generate_report(session_id="sess_123", user_id="user_456")

        assert report.session_id == "sess_123"
        assert len(report.log_entries) == 4
        assert report.summary["documents_uploaded"] == 2
        assert report.summary["suggestions_generated"] == 1
        assert report.summary["suggestions_edited"] == 1
        assert report.summary["total_events"] == 4

    def test_report_retention_calculation(self, logger):
        """Test retention period is calculated correctly."""
        created_at = datetime.utcnow()
        ended_at = created_at + timedelta(hours=2)

        report = logger.generate_report(
            session_id="sess_123", created_at=created_at, ended_at=ended_at, retention_years=1
        )

        expected_retention = ended_at + timedelta(days=365)
        assert abs((report.retention_until - expected_retention).total_seconds()) < 1

    def test_report_with_consent(self, logger):
        """Test report includes consent information."""
        consent = Consent(session_id="sess_123", terms_version="1.0", privacy_version="1.0")

        logger.log_consent(session_id="sess_123", consent=consent)

        report = logger.generate_report(session_id="sess_123")

        assert report.consent is not None
        assert report.consent.terms_version == "1.0"
        assert report.consent.privacy_version == "1.0"

    def test_format_report_json(self, logger):
        """Test formatting report as JSON."""
        logger.log_upload(
            session_id="sess_123", filename="test.pdf", file_size=1000, file_type=".pdf"
        )

        report = logger.generate_report(session_id="sess_123")
        formatted = logger.format_report(report, format_type="json")

        # Should be valid JSON
        data = json.loads(formatted)
        assert data["session_id"] == "sess_123"
        assert "log_entries" in data
        assert "summary" in data

    def test_format_report_plaintext(self, logger):
        """Test formatting report as plaintext."""
        logger.log_upload(
            session_id="sess_123", filename="test.pdf", file_size=1000, file_type=".pdf"
        )

        report = logger.generate_report(session_id="sess_123", user_id="user_456")
        formatted = logger.format_report(report, format_type="plaintext")

        assert "AUDIT REPORT" in formatted
        assert "sess_123" in formatted
        assert "SUMMARY" in formatted
        assert "Documents Uploaded:" in formatted
        assert "ACTIVITY LOG" in formatted
        assert "UPLOAD" in formatted

    def test_format_audit_markdown(self, logger):
        """Test formatting audit report as Markdown."""
        logger.log_upload(
            session_id="sess_123", filename="test.pdf", file_size=1000, file_type=".pdf"
        )
        logger.log_suggestion(
            session_id="sess_123",
            question="What is your job title?",
            suggested_answer="Senior Developer based on the CV provided.",
            sources_used=["test.pdf"],
            model="anthropic/claude-3-sonnet",
        )
        logger.log_edit(
            session_id="sess_123",
            original_suggestion="Senior Developer based on the CV provided.",
            edited_version="Lead Developer",
        )

        report = logger.generate_report(session_id="sess_123")

        from cue_api.routes.audit import _format_audit_markdown

        formatted = _format_audit_markdown(report, "sess_123")

        assert "# Audit Report" in formatted
        assert "sess_123" in formatted
        assert "## Documents Uploaded" in formatted
        assert "test.pdf" in formatted
        assert "## Suggestions Generated" in formatted
        assert "What is your job title?" in formatted
        assert "Senior Developer" in formatted
        assert "## Edits" in formatted
        assert "Lead Developer" in formatted
        assert "## Summary" in formatted
        assert "**Total Documents:** 1" in formatted
        assert "**Total Suggestions:** 1" in formatted
        assert "**Total Edits:** 1" in formatted

    def test_format_audit_markdown_empty(self, logger):
        """Test Markdown format with no log entries."""
        report = logger.generate_report(session_id="sess_empty")

        from cue_api.routes.audit import _format_audit_markdown

        formatted = _format_audit_markdown(report, "sess_empty")

        assert "# Audit Report" in formatted
        assert "No documents uploaded." in formatted
        assert "No suggestions generated." in formatted
        assert "## Summary" in formatted

    def test_format_audit_markdown_pipe_escape(self, logger):
        """Test that pipe characters in filenames are escaped in Markdown tables."""
        logger.log_upload(
            session_id="sess_123", filename="file|with|pipes.pdf", file_size=500, file_type=".pdf"
        )

        report = logger.generate_report(session_id="sess_123")

        from cue_api.routes.audit import _format_audit_markdown

        formatted = _format_audit_markdown(report, "sess_123")

        assert "file\\|with\\|pipes.pdf" in formatted

    def test_mark_claimed(self, logger, temp_dir):
        """Test marking report as claimed."""
        logger.log_upload(
            session_id="sess_123", filename="test.pdf", file_size=1000, file_type=".pdf"
        )

        assert not logger.is_claimed("sess_123")

        logger.mark_claimed("sess_123")

        assert logger.is_claimed("sess_123")

        # Verify claim file exists
        claim_path = Path(temp_dir) / "sess_123" / "report_claimed.json"
        assert claim_path.exists()

    def test_is_claimed_nonexistent(self, logger):
        """Test checking claimed status for nonexistent session."""
        assert not logger.is_claimed("nonexistent_session")

    def test_delete_report_removes_audit_log(self, logger):
        """delete_report() removes audit_log.json."""
        logger.log_upload(
            session_id="sess_123", filename="doc.pdf", file_size=1000, file_type=".pdf"
        )
        log_path = logger._get_audit_log_path("sess_123")
        assert log_path.exists()

        logger.delete_report("sess_123")

        assert not log_path.exists()

    def test_delete_report_removes_claimed_marker(self, logger):
        """delete_report() also removes report_claimed.json."""
        logger.log_upload(
            session_id="sess_123", filename="doc.pdf", file_size=1000, file_type=".pdf"
        )
        logger.mark_claimed("sess_123")
        assert logger.is_claimed("sess_123")

        logger.delete_report("sess_123")

        assert not logger.is_claimed("sess_123")

    def test_delete_report_writes_tombstone(self, logger, temp_dir):
        """delete_report() writes report_deleted.json tombstone."""
        logger.log_upload(
            session_id="sess_123", filename="doc.pdf", file_size=1000, file_type=".pdf"
        )

        logger.delete_report("sess_123")

        tombstone_path = Path(temp_dir) / "sess_123" / "report_deleted.json"
        assert tombstone_path.exists()
        data = json.loads(tombstone_path.read_text())
        assert data["session_id"] == "sess_123"
        assert "deleted_at" in data

    def test_delete_report_tombstone_contains_no_personal_data(self, logger, temp_dir):
        """Tombstone must not contain audit entries or user content."""
        logger.log_suggestion(
            session_id="sess_123",
            question="What is my salary?",
            suggested_answer="€50,000",
            sources_used=["contract.pdf"],
            model="test-model",
        )

        logger.delete_report("sess_123")

        tombstone_path = Path(temp_dir) / "sess_123" / "report_deleted.json"
        tombstone_text = tombstone_path.read_text()
        assert "salary" not in tombstone_text
        assert "50,000" not in tombstone_text
        assert "contract.pdf" not in tombstone_text

    def test_is_deleted_false_by_default(self, logger):
        """is_deleted() returns False when no deletion has occurred."""
        assert not logger.is_deleted("sess_123")

    def test_is_deleted_true_after_delete_report(self, logger):
        """is_deleted() returns True after delete_report() is called."""
        logger.log_upload(
            session_id="sess_123", filename="doc.pdf", file_size=1000, file_type=".pdf"
        )
        logger.delete_report("sess_123")
        assert logger.is_deleted("sess_123")

    def test_delete_report_idempotent_when_no_log(self, logger):
        """delete_report() is safe to call even when no audit log exists."""
        logger.delete_report("sess_no_log")
        assert logger.is_deleted("sess_no_log")


class TestAuditReportModel:
    """Tests for AuditReport Pydantic model."""

    def test_create_report(self):
        """Test creating an audit report model."""
        created_at = datetime.utcnow()
        ended_at = created_at + timedelta(hours=2)
        retention = ended_at + timedelta(days=365)

        report = AuditReport(
            session_id="sess_123",
            user_id="user_456",
            created_at=created_at,
            ended_at=ended_at,
            retention_until=retention,
            summary={"documents_uploaded": 2},
        )

        assert report.session_id == "sess_123"
        assert report.user_id == "user_456"
        assert not report.is_claimed
        assert len(report.log_entries) == 0

    def test_report_serialization(self):
        """Test report serializes correctly."""
        report = AuditReport(
            session_id="sess_123",
            created_at=datetime.utcnow(),
            retention_until=datetime.utcnow() + timedelta(days=365),
            summary={"test": "value"},
        )

        data = report.model_dump(mode="json")

        assert data["session_id"] == "sess_123"
        assert "created_at" in data
        assert "summary" in data
        assert data["is_claimed"] is False
