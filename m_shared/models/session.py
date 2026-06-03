"""Session model representing user session context with TTL."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _coerce_utc(value: datetime | str | None) -> datetime | None:
    """Coerce an ISO string or datetime to timezone-aware UTC.

    Session timestamps are always UTC-aware so expiry/retention comparisons never
    mix naive and aware datetimes (which raises TypeError). Naive inputs — legacy
    metadata.json or callers passing datetime.utcnow() — are assumed to be UTC.
    Aware inputs in a non-UTC zone (e.g. ISO strings with explicit offsets) are
    converted to UTC so the "UTC everywhere" invariant holds end-to-end.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        elif value.tzinfo.utcoffset(value) != UTC.utcoffset(value):
            value = value.astimezone(UTC)
    return value


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

    @model_validator(mode="before")
    @classmethod
    def _default_expiration(cls, data: Any) -> Any:
        """Derive expires_at from created_at + metadata.ttl_hours when not provided.

        Single source of truth for expiry. Runs before field validation so it can
        read created_at and metadata together (a field validator cannot, due to
        field ordering). Default TTL is 24h.
        """
        if isinstance(data, dict) and data.get("expires_at") is None:
            created_at = _coerce_utc(data.get("created_at")) or datetime.now(UTC)
            ttl_hours = (data.get("metadata") or {}).get("ttl_hours", 24)
            data = {
                **data,
                "created_at": created_at,
                "expires_at": created_at + timedelta(hours=ttl_hours),
            }
        return data

    @field_validator("created_at", "expires_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Normalise each timestamp to timezone-aware UTC (see _coerce_utc)."""
        return _coerce_utc(v)

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
