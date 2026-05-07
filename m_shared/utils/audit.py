"""Audit logging for Cue session transparency and compliance.

Provides session-level audit trails capturing all user activity:
- Document uploads
- Suggestion generation (with sources)
- User edits to suggestions
- Session lifecycle events

Audit reports enable users to verify which documents informed their answers,
supporting GDPR Right to Know and building user trust.
"""

import json
import threading
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(str, Enum):
    """Types of auditable events in a session."""

    UPLOAD = "UPLOAD"
    SUGGEST = "SUGGEST"
    EDIT_SUGGESTION = "EDIT_SUGGESTION"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    CONSENT_ACCEPTED = "CONSENT_ACCEPTED"


class AuditLogEntry(BaseModel):
    """Single audit log entry recording an event.

    Examples:
        >>> entry = AuditLogEntry(
        ...     event_type=AuditEventType.UPLOAD,
        ...     session_id="sess_123",
        ...     timestamp=datetime.utcnow(),
        ...     details={"filename": "cv.pdf", "file_size": 50000}
        ... )
    """

    event_type: AuditEventType = Field(..., description="Type of event")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When event occurred"
    )
    user_id: str | None = Field(None, description="User who triggered the event")
    details: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "SUGGEST",
                "session_id": "sess_abc123",
                "timestamp": "2026-01-12T10:30:00Z",
                "user_id": "user_456",
                "details": {
                    "question": "What is my job title?",
                    "suggested_answer": "Senior Developer",
                    "sources_used": ["employment_contract.pdf"],
                    "model": "anthropic/claude-3-sonnet",
                },
            }
        }
    )


class Consent(BaseModel):
    """User consent record for session data handling.

    Examples:
        >>> consent = Consent(
        ...     session_id="sess_123",
        ...     accepted_at=datetime.utcnow(),
        ...     terms_version="1.0",
        ...     privacy_version="1.0"
        ... )
    """

    session_id: str = Field(..., description="Session identifier")
    accepted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When consent was given"
    )
    terms_version: str = Field(..., description="Version of terms accepted")
    privacy_version: str = Field(..., description="Version of privacy policy accepted")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "accepted_at": "2026-01-12T10:00:00Z",
                "terms_version": "1.0",
                "privacy_version": "1.0",
            }
        }
    )


class AuditReport(BaseModel):
    """Complete audit report for a session.

    Generated on demand or at session end, provides full traceability
    of all session activity for user review.

    Examples:
        >>> report = AuditReport(
        ...     session_id="sess_123",
        ...     created_at=datetime.utcnow(),
        ...     ended_at=datetime.utcnow(),
        ...     retention_until=datetime.utcnow() + timedelta(days=365),
        ...     log_entries=[...],
        ...     summary={"documents_uploaded": 2, "suggestions_generated": 5}
        ... )
    """

    session_id: str = Field(..., description="Session identifier")
    user_id: str | None = Field(None, description="User who owned the session")
    created_at: datetime = Field(..., description="Session start time")
    ended_at: datetime | None = Field(None, description="Session end time (if ended)")
    retention_until: datetime = Field(..., description="When report will be auto-deleted")
    is_claimed: bool = Field(default=False, description="Whether user has downloaded report")
    log_entries: list[AuditLogEntry] = Field(
        default_factory=list, description="All audit log entries"
    )
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics")
    consent: Consent | None = Field(None, description="Consent record")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "user_id": "user_456",
                "created_at": "2026-01-12T10:00:00Z",
                "ended_at": "2026-01-12T11:30:00Z",
                "retention_until": "2027-01-12T11:30:00Z",
                "is_claimed": False,
                "summary": {
                    "documents_uploaded": 3,
                    "suggestions_generated": 7,
                    "suggestions_edited": 2,
                },
            }
        }
    )


class AuditLogger:
    """Thread-safe audit logger for session activity.

    Stores audit logs as JSON files in session directories:
    sessions/{session_id}/audit_log.json

    Examples:
        >>> logger = AuditLogger(base_path="./sessions")
        >>> logger.log_upload(
        ...     session_id="sess_123",
        ...     filename="cv.pdf",
        ...     file_size=50000
        ... )
        >>> logger.log_suggestion(
        ...     session_id="sess_123",
        ...     question="What is my title?",
        ...     suggested_answer="Senior Developer",
        ...     sources_used=["cv.pdf"]
        ... )
    """

    def __init__(self, base_path: str = "./sessions"):
        """Initialize audit logger.

        Args:
            base_path: Base directory for session folders
        """
        self.base_path = Path(base_path)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def _get_lock(self, session_id: str) -> threading.Lock:
        """Get or create a lock for a session.

        Args:
            session_id: Session identifier

        Returns:
            Threading lock for this session
        """
        with self._locks_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.Lock()
            return self._locks[session_id]

    def _get_audit_log_path(self, session_id: str) -> Path:
        """Get path to audit log file for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to audit_log.json
        """
        return self.base_path / session_id / "audit_log.json"

    def _load_entries(self, session_id: str) -> list[AuditLogEntry]:
        """Load existing audit log entries for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of audit log entries (empty if file doesn't exist)
        """
        log_path = self._get_audit_log_path(session_id)
        if not log_path.exists():
            return []

        with open(log_path) as f:
            data = json.load(f)

        return [AuditLogEntry(**entry) for entry in data]

    def _save_entries(self, session_id: str, entries: list[AuditLogEntry]) -> None:
        """Save audit log entries to file.

        Args:
            session_id: Session identifier
            entries: List of audit log entries to save
        """
        log_path = self._get_audit_log_path(session_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON-serializable format
        data = [entry.model_dump(mode="json") for entry in entries]

        with open(log_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _add_entry(self, entry: AuditLogEntry) -> None:
        """Add an audit log entry (thread-safe).

        Args:
            entry: Audit log entry to add
        """
        lock = self._get_lock(entry.session_id)
        with lock:
            entries = self._load_entries(entry.session_id)
            entries.append(entry)
            self._save_entries(entry.session_id, entries)

    def log_upload(
        self,
        session_id: str,
        filename: str,
        file_size: int,
        file_type: str,
        user_id: str | None = None,
    ) -> None:
        """Log a document upload event.

        Args:
            session_id: Session identifier
            filename: Name of uploaded file
            file_size: Size in bytes
            file_type: MIME type or file extension
            user_id: Optional user identifier
        """
        entry = AuditLogEntry(
            event_type=AuditEventType.UPLOAD,
            session_id=session_id,
            user_id=user_id,
            details={"filename": filename, "file_size": file_size, "file_type": file_type},
        )
        self._add_entry(entry)

    def log_suggestion(
        self,
        session_id: str,
        question: str,
        suggested_answer: str,
        sources_used: list[str],
        model: str,
        user_id: str | None = None,
        question_id: str | None = None,
        rewritten_query: str | None = None,
    ) -> None:
        """Log an answer suggestion generation event.

        Args:
            session_id: Session identifier
            question: Question text
            suggested_answer: Generated answer
            sources_used: List of source document names
            model: LLM model used for generation
            user_id: Optional user identifier
            question_id: Optional question identifier
            rewritten_query: Optional rewritten search query used for retrieval
        """
        details = {
            "question": question,
            "question_id": question_id,
            "suggested_answer": suggested_answer,
            "sources_used": sources_used,
            "model": model,
            "source_count": len(sources_used),
        }
        if rewritten_query is not None:
            details["rewritten_query"] = rewritten_query
        entry = AuditLogEntry(
            event_type=AuditEventType.SUGGEST,
            session_id=session_id,
            user_id=user_id,
            details=details,
        )
        self._add_entry(entry)

    def log_edit(
        self,
        session_id: str,
        original_suggestion: str,
        edited_version: str,
        question: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Log a user edit to a suggestion.

        Args:
            session_id: Session identifier
            original_suggestion: Original LLM-generated answer
            edited_version: User's edited version
            question: Optional question text for context
            user_id: Optional user identifier
        """
        entry = AuditLogEntry(
            event_type=AuditEventType.EDIT_SUGGESTION,
            session_id=session_id,
            user_id=user_id,
            details={
                "question": question,
                "original_suggestion": original_suggestion,
                "edited_version": edited_version,
                "edit_type": "user_modification",
            },
        )
        self._add_entry(entry)

    def log_session_event(
        self,
        session_id: str,
        event_type: AuditEventType,
        user_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log a session lifecycle event.

        Args:
            session_id: Session identifier
            event_type: SESSION_START, SESSION_END, or CONSENT_ACCEPTED
            user_id: Optional user identifier
            reason: Optional reason (e.g., "timeout", "user_logout")
        """
        details = {}
        if reason:
            details["reason"] = reason

        entry = AuditLogEntry(
            event_type=event_type, session_id=session_id, user_id=user_id, details=details
        )
        self._add_entry(entry)

    def log_consent(self, session_id: str, consent: Consent, user_id: str | None = None) -> None:
        """Log consent acceptance.

        Args:
            session_id: Session identifier
            consent: Consent object with version info
            user_id: Optional user identifier
        """
        entry = AuditLogEntry(
            event_type=AuditEventType.CONSENT_ACCEPTED,
            session_id=session_id,
            user_id=user_id,
            details={
                "terms_version": consent.terms_version,
                "privacy_version": consent.privacy_version,
                "accepted_at": consent.accepted_at.isoformat(),
            },
        )
        self._add_entry(entry)

    def get_entries(self, session_id: str) -> list[AuditLogEntry]:
        """Get all audit log entries for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of audit log entries (chronological order)
        """
        return self._load_entries(session_id)

    def generate_report(
        self,
        session_id: str,
        user_id: str | None = None,
        created_at: datetime | None = None,
        ended_at: datetime | None = None,
        retention_years: int = 1,
    ) -> AuditReport:
        """Generate a complete audit report for a session.

        Args:
            session_id: Session identifier
            user_id: Optional user identifier
            created_at: Session creation time (defaults to first log entry)
            ended_at: Session end time (defaults to last log entry)
            retention_years: Years to retain report (default: 1)

        Returns:
            Complete audit report
        """
        entries = self.get_entries(session_id)

        # Determine timestamps
        if not created_at and entries:
            created_at = entries[0].timestamp
        elif not created_at:
            created_at = datetime.now(UTC)

        if not ended_at and entries:
            ended_at = entries[-1].timestamp

        # Calculate retention
        retention_until = (ended_at or datetime.now(UTC)) + timedelta(days=365 * retention_years)

        # Generate summary statistics
        summary = {
            "total_events": len(entries),
            "documents_uploaded": sum(1 for e in entries if e.event_type == AuditEventType.UPLOAD),
            "suggestions_generated": sum(
                1 for e in entries if e.event_type == AuditEventType.SUGGEST
            ),
            "suggestions_edited": sum(
                1 for e in entries if e.event_type == AuditEventType.EDIT_SUGGESTION
            ),
        }

        # Extract consent if present
        consent = None
        consent_entries = [e for e in entries if e.event_type == AuditEventType.CONSENT_ACCEPTED]
        if consent_entries:
            consent_data = consent_entries[0].details
            consent = Consent(
                session_id=session_id,
                accepted_at=datetime.fromisoformat(consent_data["accepted_at"]),
                terms_version=consent_data["terms_version"],
                privacy_version=consent_data["privacy_version"],
            )

        return AuditReport(
            session_id=session_id,
            user_id=user_id,
            created_at=created_at,
            ended_at=ended_at,
            retention_until=retention_until,
            log_entries=entries,
            summary=summary,
            consent=consent,
        )

    def format_report(self, report: AuditReport, format_type: str = "json") -> str:
        """Format an audit report for user download.

        Args:
            report: AuditReport to format
            format_type: "json" or "plaintext"

        Returns:
            Formatted report string
        """
        if format_type == "json":
            return report.model_dump_json(indent=2)

        # Plaintext format
        lines = [
            "=" * 70,
            f"AUDIT REPORT: Session {report.session_id}",
            "=" * 70,
            "",
            f"Created:   {report.created_at.isoformat()}",
            f"Ended:     {report.ended_at.isoformat() if report.ended_at else 'Ongoing'}",
            f"User:      {report.user_id or 'Unknown'}",
            f"Retention: {report.retention_until.isoformat()}",
            "",
            "SUMMARY",
            "-" * 70,
            f"  Documents Uploaded:     {report.summary.get('documents_uploaded', 0)}",
            f"  Suggestions Generated:  {report.summary.get('suggestions_generated', 0)}",
            f"  Suggestions Edited:     {report.summary.get('suggestions_edited', 0)}",
            f"  Total Events:           {report.summary.get('total_events', 0)}",
            "",
            "ACTIVITY LOG",
            "-" * 70,
        ]

        for entry in report.log_entries:
            lines.append(f"\n[{entry.timestamp.isoformat()}] {entry.event_type.value}")
            for key, value in entry.details.items():
                lines.append(f"  {key}: {value}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def mark_claimed(self, session_id: str) -> None:
        """Mark an audit report as claimed (user downloaded).

        Note: This is stored separately from audit_log.json to avoid
        modifying immutable audit logs.

        Args:
            session_id: Session identifier
        """
        claim_path = self.base_path / session_id / "report_claimed.json"
        claim_path.parent.mkdir(parents=True, exist_ok=True)

        with open(claim_path, "w") as f:
            json.dump({"claimed_at": datetime.now(UTC).isoformat(), "session_id": session_id}, f)

    def is_claimed(self, session_id: str) -> bool:
        """Check if audit report has been claimed.

        Args:
            session_id: Session identifier

        Returns:
            True if report was downloaded by user
        """
        claim_path = self.base_path / session_id / "report_claimed.json"
        return claim_path.exists()

    def delete_report(self, session_id: str) -> None:
        """Delete audit report for a session (GDPR Right to Erasure).

        Removes the audit log and any claimed marker, then writes a tombstone
        recording that erasure was requested. The tombstone contains no personal
        data — only the session_id and deletion timestamp.

        A new audit log will be created if the session continues to be used
        after deletion; this is intentional (working as designed for PoC).

        Args:
            session_id: Session identifier
        """
        with self._get_lock(session_id):
            session_dir = self.base_path / session_id

            log_path = self._get_audit_log_path(session_id)
            if log_path.exists():
                log_path.unlink()

            claim_path = session_dir / "report_claimed.json"
            if claim_path.exists():
                claim_path.unlink()

            tombstone_path = session_dir / "report_deleted.json"
            tombstone_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tombstone_path, "w") as f:
                json.dump(
                    {
                        "session_id": session_id,
                        "deleted_at": datetime.now(UTC).isoformat(),
                    },
                    f,
                )

    def is_deleted(self, session_id: str) -> bool:
        """Check if audit report has been explicitly deleted (RTBF).

        Args:
            session_id: Session identifier

        Returns:
            True if delete_report() was called for this session
        """
        return (self.base_path / session_id / "report_deleted.json").exists()
