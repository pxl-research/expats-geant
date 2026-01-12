"""Survey model representing a complete questionnaire."""

from typing import Any

from pydantic import BaseModel, Field

from m_shared.models.section import Section


class Survey(BaseModel):
    """Represents a complete survey/questionnaire with sections and metadata.
    
    Surveys contain one or more sections, each with questions.
    
    Examples:
        >>> survey = Survey(
        ...     id="survey_1",
        ...     title="Employee Satisfaction Survey",
        ...     description="Annual feedback survey",
        ...     sections=[
        ...         Section(id="sec_1", title="Demographics", questions=[]),
        ...         Section(id="sec_2", title="Satisfaction", questions=[])
        ...     ]
        ... )
    """
    
    id: str = Field(..., description="Unique identifier for this survey")
    title: str = Field(..., description="Survey title")
    description: str = Field("", description="Survey description or introduction text")
    sections: list[Section] = Field(default_factory=list, description="Sections contained in this survey")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata (author, version, tags, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "survey_1",
                "title": "Employee Satisfaction Survey",
                "description": "Annual feedback survey for all employees",
                "sections": [],
                "metadata": {"version": "1.0", "author": "HR Department"}
            }
        }
