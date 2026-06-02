"""Session model representing user session context with TTL."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Session(BaseModel):
    """Represents a user session with time-to-live (TTL) for data expiration.

    Sessions provide isolation boundaries for user data and enable automatic cleanup.

    Examples:
        >>> session = Session(
        ...     session_id="sess_abc123",
        ...     user_id="user_456",
        ...     ttl_hours=24
        ... )
        >>> session.is_expired()
        False
    """

    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="ID of the user who owns this session")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When this session was created"
    )
    expires_at: datetime = Field(
        ..., description="When this session expires and data should be deleted"
    )
    isolation_scope: str = Field("user", description="Scope of data isolation (user, org, tenant)")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional session metadata"
    )

    @field_validator("created_at", "expires_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Coerce ISO strings and naive datetimes to timezone-aware UTC.

        All session timestamps are UTC-aware so expiry/retention comparisons never
        mix naive and aware datetimes (which raises TypeError). Naive inputs — e.g.
        legacy metadata.json or callers passing datetime.utcnow() — are assumed UTC.
        """
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if isinstance(v, datetime) and v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v

    def __init__(self, **data):
        """Initialize session, computing TTL-based expiration if not provided.

        This is the single source of truth for expires_at: it reads ttl_hours from
        metadata (default 24h). Used on both fresh creation and metadata reload
        (SessionManager constructs via ``Session(**data)``).
        """
        if data.get("expires_at") is None:
            ttl_hours = data.get("metadata", {}).get("ttl_hours", 24)
            created_at = data.get("created_at") or datetime.now(UTC)
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            data["created_at"] = created_at
            data["expires_at"] = created_at + timedelta(hours=ttl_hours)
        super().__init__(**data)

    def is_expired(self) -> bool:
        """Check if this session has expired."""
        return datetime.now(UTC) >= self.expires_at

    def time_remaining(self) -> timedelta:
        """Calculate time remaining until expiration."""
        return self.expires_at - datetime.now(UTC)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "user_id": "user_456",
                "created_at": "2026-01-08T10:00:00Z",
                "expires_at": "2026-01-09T10:00:00Z",
                "isolation_scope": "user",
                "metadata": {"ttl_hours": 24, "org": "pxl"},
            }
        }
    )
