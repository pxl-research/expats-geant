"""Question model supporting five core QTI 3.0-compatible question types."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from m_shared.models.answer_option import AnswerOption


class QuestionType(str, Enum):
    """Supported question types for MVP."""

    MULTIPLE_CHOICE = "multiple_choice"
    SINGLE_CHOICE = "single_choice"
    OPEN_ENDED = "open_ended"
    RANKING = "ranking"
    SLIDER = "slider"


class Question(BaseModel):
    """Represents a single question in a survey.

    Supports five core question types:
    - multiple_choice: User selects multiple options
    - single_choice: User selects one option (includes Likert scales, yes/no)
    - open_ended: User provides free-text response
    - ranking: User orders options by preference
    - slider: User selects a numeric value within a range

    Examples:
        >>> # Single choice (Likert scale)
        >>> q = Question(
        ...     id="q1",
        ...     text="How satisfied are you?",
        ...     type=QuestionType.SINGLE_CHOICE,
        ...     answer_options=[
        ...         AnswerOption(id="opt_1", text="Very satisfied", value=5),
        ...         AnswerOption(id="opt_2", text="Satisfied", value=4),
        ...     ]
        ... )

        >>> # Slider question
        >>> q = Question(
        ...     id="q2",
        ...     text="Rate your experience (0-100)",
        ...     type=QuestionType.SLIDER,
        ...     min_value=0,
        ...     max_value=100,
        ...     step=1
        ... )
    """

    id: str = Field(..., description="Unique identifier for this question")
    text: str = Field(..., description="Question text displayed to the user")
    type: QuestionType = Field(
        ...,
        description="Question type (multiple_choice, single_choice, open_ended, ranking, slider)",
    )
    answer_options: list[AnswerOption] = Field(
        default_factory=list, description="Predefined answer options (for choice/ranking questions)"
    )
    min_value: float | None = Field(None, description="Minimum value for slider questions")
    max_value: float | None = Field(None, description="Maximum value for slider questions")
    step: float | None = Field(None, description="Step increment for slider questions")
    required: bool = Field(True, description="Whether this question requires an answer")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (tags, hints, validation rules)"
    )

    @field_validator("answer_options")
    @classmethod
    def validate_answer_options(cls, v: list[AnswerOption], info) -> list[AnswerOption]:
        """Validate that choice/ranking questions have answer options."""
        question_type = info.data.get("type")
        if question_type in [
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.SINGLE_CHOICE,
            QuestionType.RANKING,
        ]:
            if not v:
                raise ValueError(
                    f"Question type '{question_type}' requires at least one answer option"
                )
        return v

    @model_validator(mode="after")
    def validate_slider_requirements(self) -> "Question":
        """Validate that slider questions have min/max values."""
        if self.type == QuestionType.SLIDER:
            if self.min_value is None or self.max_value is None:
                raise ValueError("Slider questions must have min_value and max_value")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "id": "q1",
                "text": "How satisfied are you with this service?",
                "type": "single_choice",
                "answer_options": [
                    {"id": "opt_1", "text": "Very satisfied", "value": 5},
                    {"id": "opt_2", "text": "Satisfied", "value": 4},
                    {"id": "opt_3", "text": "Neutral", "value": 3},
                ],
                "required": True,
                "metadata": {"category": "satisfaction"},
            }
        }
