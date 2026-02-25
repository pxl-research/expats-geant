"""Section model representing a page or grouping within a survey."""

from typing import Any

from pydantic import BaseModel, Field

from m_shared.models.question import Question


class Section(BaseModel):
    """Represents a section (page or grouping) within a survey.

    Sections enable logical grouping and pagination of questions.

    Examples:
        >>> section = Section(
        ...     id="sec_1",
        ...     title="Demographics",
        ...     description="Please provide some basic information",
        ...     questions=[
        ...         Question(id="q1", text="What is your age?", type="open_ended")
        ...     ]
        ... )
    """

    id: str = Field(..., description="Unique identifier for this section")
    title: str = Field(..., description="Section title displayed to the user")
    description: str = Field(
        "", description="Optional description or instructions for this section"
    )
    questions: list[Question] = Field(
        default_factory=list, description="Questions contained in this section"
    )
    order: int = Field(0, description="Display order of this section within the survey")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for this section"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "sec_1",
                "title": "Demographics",
                "description": "Tell us about yourself",
                "questions": [],
                "order": 1,
                "metadata": {},
            }
        }
