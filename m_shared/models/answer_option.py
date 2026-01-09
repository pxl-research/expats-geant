"""Answer option model for questions with predefined choices."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class AnswerOption(BaseModel):
    """Represents a single answer choice for multiple choice, single choice, or ranking questions.
    
    Examples:
        >>> option = AnswerOption(id="opt_1", text="Strongly Agree", value=5)
        >>> option.text
        'Strongly Agree'
    """
    
    id: str = Field(..., description="Unique identifier for this answer option")
    text: str = Field(..., description="Display text for the answer option")
    value: Optional[Any] = Field(None, description="Optional value associated with this option (e.g., numeric score)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata for this option")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "opt_1",
                "text": "Strongly Agree",
                "value": 5,
                "metadata": {"color": "green"}
            }
        }
