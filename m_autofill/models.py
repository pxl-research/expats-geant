"""Pydantic models for M-Autofill batch suggest endpoint."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from m_shared.models.question import QuestionType


class BatchChoice(BaseModel):
    """A selectable choice within a question."""

    id: str = Field(..., description="Choice identifier, echoed back in selected_id")
    label: str = Field(..., description="Human-readable choice text")


class BatchSuggestItem(BaseModel):
    """A single questionnaire item in a batch suggest request."""

    id: str = Field(..., description="Item identifier, echoed back in response")
    type: QuestionType = Field(..., description="Question type")
    prompt: str = Field(..., min_length=1, max_length=2000, description="Question text")
    choices: list[BatchChoice] = Field(
        default_factory=list,
        description="Predefined choices (required for single_choice and multiple_choice types)",
    )

    @model_validator(mode="after")
    def validate_choices_for_type(self) -> "BatchSuggestItem":
        """Enforce choices are present for choice types and absent for open-ended."""
        choice_types = {QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE}
        if self.type in choice_types and not self.choices:
            raise ValueError(f"'choices' must be non-empty for type '{self.type}'")
        if self.type not in choice_types and self.choices:
            raise ValueError(f"'choices' must be empty for type '{self.type}'")
        return self


class BatchSuggestSection(BaseModel):
    """A group of related questionnaire items sharing context."""

    id: str = Field(..., description="Section identifier")
    title: Optional[str] = Field(None, description="Section title, used as LLM context")
    items: list[BatchSuggestItem] = Field(..., min_length=1, description="Items in this section")


class BatchSuggestRequest(BaseModel):
    """Request for batch answer suggestions.

    Accepts either a structured `sections` list or a flat `items` list.
    Flat items are normalized to a single implicit section internally.

    Examples:
        >>> # Sectioned input
        >>> req = BatchSuggestRequest(
        ...     assessment_id="gdpr-2026",
        ...     sections=[BatchSuggestSection(id="s1", title="Data Retention", items=[...])]
        ... )
        >>> # Flat input
        >>> req = BatchSuggestRequest(
        ...     assessment_id="quick-check",
        ...     items=[BatchSuggestItem(id="q1", type="open_ended", prompt="...")]
        ... )
    """

    assessment_id: str = Field(..., description="Caller-supplied assessment identifier, echoed in response")
    context: Optional[str] = Field(None, max_length=1000, description="Optional assessment-level context for the LLM")
    sections: Optional[list[BatchSuggestSection]] = Field(None, description="Grouped items (use this or items, not both)")
    items: Optional[list[BatchSuggestItem]] = Field(None, description="Flat item list (normalized to single implicit section)")

    @model_validator(mode="after")
    def validate_items_or_sections(self) -> "BatchSuggestRequest":
        """Ensure exactly one of sections or items is provided."""
        has_sections = bool(self.sections)
        has_items = bool(self.items)
        if not has_sections and not has_items:
            raise ValueError("Provide either 'sections' or 'items'")
        if has_sections and has_items:
            raise ValueError("Provide either 'sections' or 'items', not both")
        return self


class CitationResult(BaseModel):
    """A citation linking a suggestion to a source document fragment."""

    source: str = Field(..., description="Source document filename")
    excerpt: str = Field(..., description="Exact text excerpt from the source (W3C TextQuoteSelector pattern)")
    position: float = Field(..., ge=0.0, le=1.0, description="Normalized position in document (0.0–1.0)")


class ItemSuggestion(BaseModel):
    """Suggestion for a single questionnaire item."""

    item_id: str = Field(..., description="Matches the input item id")
    type: str = Field(..., description="Question type, echoed from input")
    suggestion: str = Field(..., description="Human-readable answer, safe to display directly")
    selected_id: Optional[str] = Field(None, description="Matched choice id for single_choice (null if uncertain)")
    selected_ids: Optional[list[str]] = Field(None, description="Matched choice ids for multiple_choice (null if uncertain)")
    reasoning: Optional[str] = Field(None, description="LLM explanation of confidence, source interpretation, or uncertainty")
    citations: list[CitationResult] = Field(default_factory=list, description="Source citations for this suggestion")


class BatchSuggestResponse(BaseModel):
    """Response for a batch suggest request."""

    assessment_id: str = Field(..., description="Echoed from request")
    session_id: str
    generated_at: str = Field(..., description="ISO 8601 timestamp of generation")
    model: str = Field(..., description="LLM model used for generation")
    responses: list[ItemSuggestion]


def normalize_to_sections(request: BatchSuggestRequest) -> list[BatchSuggestSection]:
    """Normalize a batch request to a list of sections.

    Flat top-level items are wrapped in a single implicit section.

    Args:
        request: Validated batch suggest request

    Returns:
        List of sections ready for processing
    """
    if request.sections:
        return request.sections
    return [BatchSuggestSection(id="_implicit", items=request.items)]
