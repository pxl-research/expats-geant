"""Session manager for handling user sessions with TTL and isolated storage."""

import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from m_shared.models.session import Session
from m_shared.utils import AuditEventType, AuditLogger, Consent
from m_shared.vectordb import ChromaDocumentStore


class SessionManager:
    """Manages user sessions with isolated ChromaDB storage and TTL-based cleanup.

    Each session gets its own folder with:
    - metadata.json: Session info (created_at, expires_at, user_id)
    - chroma_store/: ChromaDB SQLite files
    - uploads/: Optional uploaded file storage

    Session IDs are derived from hashed JWT tokens for stability and security.

    Examples:
        >>> manager = SessionManager(base_path="./sessions")
        >>> session = manager.create_session(user_id="user_123", jwt_token="abc...")
        >>> store = manager.get_vector_store(session.session_id)
        >>> store.add_document(...)
    """

    def __init__(self, base_path: str = "./sessions"):
        """Initialize session manager.

        Args:
            base_path: Base directory for all session folders
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.audit_logger = AuditLogger(base_path=base_path)
        self._vector_store_cache: dict[str, ChromaDocumentStore] = {}

    def _hash_token(self, jwt_token: str) -> str:
        """Generate stable session_id from JWT token.

        Args:
            jwt_token: JWT token string

        Returns:
            16-character hex hash of the token
        """
        return hashlib.sha256(jwt_token.encode()).hexdigest()[:16]

    def _get_session_path(self, session_id: str) -> Path:
        """Get path to session folder.

        Args:
            session_id: Unique session identifier

        Returns:
            Path to session directory
        """
        return self.base_path / session_id

    def _save_session_metadata(self, session: Session) -> None:
        """Save session metadata to JSON file.

        Args:
            session: Session object to save
        """
        session_path = self._get_session_path(session.session_id)
        metadata_path = session_path / "metadata.json"

        metadata = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "isolation_scope": session.isolation_scope,
            "metadata": session.metadata,
        }

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def _load_session_metadata(self, session_id: str) -> Session | None:
        """Load session metadata from JSON file.

        Args:
            session_id: Session identifier

        Returns:
            Session object if exists, None otherwise
        """
        session_path = self._get_session_path(session_id)
        metadata_path = session_path / "metadata.json"

        if not metadata_path.exists():
            return None

        with open(metadata_path) as f:
            data = json.load(f)

        # Parse datetime strings
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["expires_at"] = datetime.fromisoformat(data["expires_at"])

        return Session(**data)

    def create_session(
        self,
        user_id: str,
        jwt_token: str,
        ttl_hours: int = 24,
        isolation_scope: str = "user",
        consent: Consent | None = None,
        terms_version: str = "1.0",
        privacy_version: str = "1.0",
        explicit_session_id: str | None = None,
        session_type: str | None = None,
    ) -> Session:
        """Create a new session with isolated storage.

        Args:
            user_id: ID of the user owning this session
            jwt_token: JWT token to hash for session_id
            ttl_hours: Time-to-live in hours (default: 24)
            isolation_scope: Data isolation scope (default: "user")
            consent: Optional pre-created Consent object
            terms_version: Terms version if consent not provided (default: "1.0")
            privacy_version: Privacy policy version if consent not provided (default: "1.0")
            explicit_session_id: Optional explicit session ID (skips JWT hash derivation)
            session_type: Optional session type tag (e.g. "chat", "autofill")

        Returns:
            Created Session object

        Raises:
            FileExistsError: If session already exists and is not expired
        """
        session_id = explicit_session_id or self._hash_token(jwt_token)
        session_path = self._get_session_path(session_id)

        # Check if session already exists
        if session_path.exists():
            existing = self._load_session_metadata(session_id)
            if existing and not existing.is_expired():
                # Session still valid, return it
                return existing
            # Expired session, clean it up
            self.delete_session(session_id)

        # Create session folder structure
        session_path.mkdir(parents=True, exist_ok=True)
        (session_path / "chroma_store").mkdir(exist_ok=True)
        (session_path / "uploads").mkdir(exist_ok=True)

        # Create session object
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(hours=ttl_hours)

        meta: dict = {"ttl_hours": ttl_hours}
        if session_type is not None:
            meta["session_type"] = session_type

        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=created_at,
            expires_at=expires_at,
            isolation_scope=isolation_scope,
            metadata=meta,
        )

        # Save metadata
        self._save_session_metadata(session)

        # Log session start
        self.audit_logger.log_session_event(
            session_id=session_id, event_type=AuditEventType.SESSION_START, user_id=user_id
        )

        # Log consent
        if consent is None:
            consent = Consent(
                session_id=session_id,
                accepted_at=created_at,
                terms_version=terms_version,
                privacy_version=privacy_version,
            )
        self.audit_logger.log_consent(session_id=session_id, consent=consent, user_id=user_id)

        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object if exists and not expired, None otherwise
        """
        session = self._load_session_metadata(session_id)
        if session and session.is_expired():
            return None
        return session

    def get_vector_store(self, session_id: str) -> ChromaDocumentStore:
        """Get ChromaDB store for a session.

        Args:
            session_id: Session identifier

        Returns:
            ChromaDocumentStore instance for this session

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            raise FileNotFoundError(f"Session {session_id} does not exist")

        if session_id not in self._vector_store_cache:
            chroma_path = session_path / "chroma_store"
            self._vector_store_cache[session_id] = ChromaDocumentStore(path=str(chroma_path))
        return self._vector_store_cache[session_id]

    def get_documents_path(self, session_id: str) -> Path:
        """Get path to uploads folder for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to uploads directory
        """
        return self._get_session_path(session_id) / "uploads"

    def delete_session(self, session_id: str, reason: str | None = None) -> bool:
        """Delete a session and all its data.

        Args:
            session_id: Session identifier
            reason: Optional reason for deletion (e.g., "user_request", "expired")

        Returns:
            True if session was deleted, False if it didn't exist
        """
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return False

        # Log session end before deletion
        session = self.get_session(session_id)
        if session:
            self.audit_logger.log_session_event(
                session_id=session_id,
                event_type=AuditEventType.SESSION_END,
                user_id=session.user_id,
                reason=reason,
            )

        self._vector_store_cache.pop(session_id, None)
        shutil.rmtree(session_path)
        return True

    def list_sessions(self, include_expired: bool = False) -> list[Session]:
        """List all sessions.

        Args:
            include_expired: Whether to include expired sessions

        Returns:
            List of Session objects
        """
        sessions = []

        for session_dir in self.base_path.iterdir():
            if not session_dir.is_dir():
                continue

            session = self._load_session_metadata(session_dir.name)
            if session:
                if include_expired or not session.is_expired():
                    sessions.append(session)

        return sessions

    def list_sessions_for_user(self, user_id: str, include_expired: bool = False) -> list[Session]:
        """List all sessions belonging to a specific user.

        Args:
            user_id: User identifier to filter by
            include_expired: Whether to include expired sessions

        Returns:
            List of Session objects owned by the user
        """
        return [
            s for s in self.list_sessions(include_expired=include_expired) if s.user_id == user_id
        ]

    def cleanup_expired_sessions(self) -> list[str]:
        """Remove all expired sessions.

        Also cleans up unclaimed audit reports past retention period (1 year).

        Returns:
            List of deleted session IDs
        """
        expired_sessions = [s for s in self.list_sessions(include_expired=True) if s.is_expired()]

        deleted = []
        for session in expired_sessions:
            if self.delete_session(session.session_id, reason="expired"):
                deleted.append(session.session_id)

        # Also cleanup old unclaimed audit reports
        deleted.extend(self._cleanup_old_reports())

        return deleted

    def _cleanup_old_reports(self, retention_years: int = 1) -> list[str]:
        """Clean up unclaimed audit reports past retention period.

        Args:
            retention_years: Years to retain reports (default: 1)

        Returns:
            List of cleaned up session IDs
        """
        cleaned = []
        cutoff_date = datetime.utcnow() - timedelta(days=365 * retention_years)

        for session_dir in self.base_path.iterdir():
            if not session_dir.is_dir():
                continue

            session_id = session_dir.name

            # Check if report is claimed
            if self.audit_logger.is_claimed(session_id):
                continue

            # Check report age (use last modified time of audit_log.json)
            audit_log_path = self.audit_logger._get_audit_log_path(session_id)
            if not audit_log_path.exists():
                continue

            last_modified = datetime.fromtimestamp(audit_log_path.stat().st_mtime)

            if last_modified < cutoff_date:
                # Report is old and unclaimed, delete it
                if self.delete_session(session_id, reason="retention_policy"):
                    cleaned.append(session_id)

        return cleaned

    def get_session_stats(self, session_id: str) -> dict | None:
        """Get statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with session statistics or None if session doesn't exist
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session_path = self._get_session_path(session_id)
        docs_path = session_path / "uploads"

        # Calculate remaining TTL
        now = datetime.utcnow()
        remaining = session.expires_at - now
        remaining_hours = max(0, remaining.total_seconds() / 3600)

        # Count documents
        doc_count = len(list(docs_path.iterdir())) if docs_path.exists() else 0

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "remaining_hours": round(remaining_hours, 2),
            "is_expired": session.is_expired(),
            "document_count": doc_count,
            "isolation_scope": session.isolation_scope,
        }
