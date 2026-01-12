"""Session model representing user session context with TTL."""

from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


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
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this session was created")
    expires_at: datetime = Field(..., description="When this session expires and data should be deleted")
    isolation_scope: str = Field("user", description="Scope of data isolation (user, org, tenant)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")
    
    @field_validator("expires_at", mode="before")
    @classmethod
    def set_expiration(cls, v: Optional[datetime], info) -> datetime:
        """Set expiration time based on TTL if not explicitly provided."""
        if v is not None:
            return v
        # Get TTL from context - metadata may not be available yet during validation
        # Default TTL: 24 hours
        created_at = info.data.get("created_at", datetime.utcnow())
        return created_at + timedelta(hours=24)
    
    def __init__(self, **data):
        """Initialize session with TTL-based expiration if not provided."""
        if "expires_at" not in data or data["expires_at"] is None:
            ttl_hours = data.get("metadata", {}).get("ttl_hours", 24)
            created_at = data.get("created_at", datetime.utcnow())
            data["expires_at"] = created_at + timedelta(hours=ttl_hours)
        super().__init__(**data)
    
    def is_expired(self) -> bool:
        """Check if this session has expired."""
        return datetime.utcnow() >= self.expires_at
    
    def time_remaining(self) -> timedelta:
        """Calculate time remaining until expiration."""
        return self.expires_at - datetime.utcnow()
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "user_id": "user_456",
                "created_at": "2026-01-08T10:00:00Z",
                "expires_at": "2026-01-09T10:00:00Z",
                "isolation_scope": "user",
                "metadata": {"ttl_hours": 24, "org": "pxl"}
            }
        }
