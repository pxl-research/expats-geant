"""Citation model for tracking sources in answer suggestions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Represents a citation to a source document used in answer suggestions.
    
    Citations enable transparency by tracking which documents informed each answer.
    
    Examples:
        >>> citation = Citation(
        ...     id="cite_1",
        ...     source_id="doc_abc",
        ...     chunk_id="chunk_5",
        ...     position_start=120,
        ...     position_end=450,
        ...     highlights=["relevant quote from document"]
        ... )
    """
    
    id: str = Field(..., description="Unique identifier for this citation")
    source_id: str = Field(..., description="ID of the source document")
    chunk_id: str = Field(..., description="ID of the specific chunk within the document")
    position_start: int | None = Field(None, description="Character position where cited content starts")
    position_end: int | None = Field(None, description="Character position where cited content ends")
    position_percentage: float | None = Field(None, description="Position as percentage through document (0.0-1.0)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this citation was created")
    highlights: list[str] = Field(default_factory=list, description="Highlighted excerpts from the source")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata (relevance score, context, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "cite_1",
                "source_id": "doc_abc",
                "chunk_id": "chunk_5",
                "position_start": 120,
                "position_end": 450,
                "position_percentage": 0.15,
                "timestamp": "2026-01-08T10:30:00Z",
                "highlights": ["This is the relevant excerpt from the document"],
                "metadata": {"relevance_score": 0.92}
            }
        }
