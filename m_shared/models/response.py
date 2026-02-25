"""Response model capturing user answers with metadata."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Response(BaseModel):
    """Represents a user's answer to a survey question.

    Examples:
        >>> response = Response(
        ...     id="resp_1",
        ...     question_id="q1",
        ...     answer_value="Very satisfied"
        ... )
        >>> response.timestamp
        datetime.datetime(...)
    """

    id: str = Field(..., description="Unique identifier for this response")
    question_id: str = Field(..., description="ID of the question being answered")
    answer_value: Any = Field(
        ..., description="User's answer (text, number, list of option IDs, etc.)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this response was recorded"
    )
    session_id: str | None = Field(None, description="Session ID this response belongs to")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (edit history, confidence, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "resp_1",
                "question_id": "q1",
                "answer_value": "Very satisfied",
                "timestamp": "2026-01-08T10:30:00Z",
                "session_id": "sess_abc123",
                "metadata": {},
            }
        }
    )
