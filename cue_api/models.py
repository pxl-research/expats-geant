"""Pydantic models for Cue API."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from m_shared.models.question import QuestionType


class BatchChoice(BaseModel):
    """A selectable choice within a question."""

    id: str = Field(
        ..., max_length=200, description="Choice identifier, echoed back in selected_id"
    )
    label: str = Field(..., max_length=1000, description="Human-readable choice text")


class BatchSuggestItem(BaseModel):
    """A single questionnaire item in a batch suggest request."""

    id: str = Field(..., max_length=200, description="Item identifier, echoed back in response")
    type: QuestionType = Field(..., description="Question type")
    prompt: str = Field(..., min_length=1, max_length=2000, description="Question text")
    choices: list[BatchChoice] = Field(
        default_factory=list,
        max_length=100,
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

    id: str = Field(..., max_length=200, description="Section identifier")
    title: str | None = Field(
        None, max_length=500, description="Section title, used as LLM context"
    )
    items: list[BatchSuggestItem] = Field(
        ..., min_length=1, max_length=200, description="Items in this section"
    )


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

    assessment_id: str = Field(
        ..., max_length=200, description="Caller-supplied assessment identifier, echoed in response"
    )
    context: str | None = Field(
        None, max_length=1000, description="Optional assessment-level context for the LLM"
    )
    sections: list[BatchSuggestSection] | None = Field(
        None, max_length=50, description="Grouped items (use this or items, not both)"
    )
    items: list[BatchSuggestItem] | None = Field(
        None, max_length=200, description="Flat item list (normalized to single implicit section)"
    )

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
    excerpt: str = Field(
        ..., description="Exact text excerpt from the source (W3C TextQuoteSelector pattern)"
    )
    position: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized position in document (0.0–1.0)"
    )
    distance: float = Field(
        default=0.0, description="Semantic similarity distance (lower = more relevant)"
    )
    full_text: str = Field(default="", description="Full text of the source chunk")


class ItemSuggestion(BaseModel):
    """Suggestion for a single questionnaire item."""

    item_id: str = Field(..., description="Matches the input item id")
    type: str = Field(..., description="Question type, echoed from input")
    suggestion: str | None = Field(
        None, description="Human-readable answer, or null when no relevant information found"
    )
    selected_id: str | None = Field(
        None, description="Matched choice id for single_choice (null if uncertain)"
    )
    selected_ids: list[str] | None = Field(
        None, description="Matched choice ids for multiple_choice (null if uncertain)"
    )
    reasoning: str | None = Field(
        None, description="LLM explanation of confidence, source interpretation, or uncertainty"
    )
    citations: list[CitationResult] = Field(
        default_factory=list, description="Source citations for this suggestion"
    )
    generated_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when this item was generated. None on legacy cached entries.",
    )


class BatchSuggestResponse(BaseModel):
    """Response for a batch suggest request."""

    assessment_id: str = Field(..., description="Echoed from request")
    session_id: str
    generated_at: str = Field(..., description="ISO 8601 timestamp of generation")
    model: str = Field(..., description="LLM model used for generation")
    responses: list[ItemSuggestion]


class UploadResponse(BaseModel):
    """Document upload response."""

    status: str
    filename: str
    size_bytes: int
    upload_timestamp: str
    session_id: str


class UploadTextRequest(BaseModel):
    """Request body for plain-text snippet ingestion."""

    text: str = Field(..., min_length=1, max_length=10_000_000)
    label: str | None = Field(default=None, max_length=200)


class DocumentInfo(BaseModel):
    """Info about a single ingested document."""

    name: str
    chunk_count: int
    source_kind: str | None = Field(
        default=None,
        description='Origin of the source: "file", "web", or "text". Null for chunks ingested before this field was tracked.',
    )
    source_mime: str | None = Field(
        default=None,
        description="MIME type of the original content (e.g. application/pdf, text/html). Null for chunks ingested before this field was tracked.",
    )


class SessionStatsResponse(BaseModel):
    """Session statistics response."""

    session_id: str
    user_id: str
    created_at: str
    expires_at: str
    remaining_hours: float
    is_expired: bool
    document_count: int
    documents: list[DocumentInfo] = Field(default_factory=list)
    isolation_scope: str
    last_upload_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of the most recent document or text-snippet ingestion (null if none).",
    )
    web_ingest_enabled: bool = Field(
        default=False,
        description="Whether the deployment has enabled URL-based ingestion (operator gate).",
    )
    web_consent: bool = Field(
        default=False,
        description="Whether the session has granted consent for server-side URL fetches.",
    )


class SessionDeleteResponse(BaseModel):
    """Session deletion response."""

    session_id: str
    deleted: bool
    message: str


class RemoveSourceResponse(BaseModel):
    """Response for DELETE /session/documents/{name}."""

    status: str = Field(..., description='Always "ok" on success.')
    name: str = Field(..., description="Sanitised source name that was removed.")


class AuditDeleteResponse(BaseModel):
    """Audit report deletion response."""

    session_id: str
    deleted: bool
    message: str


class LiveApiImportRequest(BaseModel):
    """Request to fetch a survey directly from a platform API."""

    format: str = Field(max_length=20)
    survey_id: str = Field(max_length=100)
    api_url: str | None = Field(default=None, max_length=500)
    api_token: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=200)
    datacenter_id: str | None = Field(default=None, max_length=50)


class ReviewStateUpdate(BaseModel):
    """Review state for a single question."""

    state: Literal["accepted", "dismissed", "edited"] = Field(..., description="Review decision")
    value: str | None = Field(default=None, max_length=10_000, description="Final text value")
    selected_id: str | None = Field(
        default=None, max_length=200, description="Selected choice ID (single_choice)"
    )
    selected_ids: list[str] | None = Field(
        default=None, max_length=100, description="Selected choice IDs (multiple_choice)"
    )


class ReviewStateResponse(BaseModel):
    """Full review state map for a session."""

    states: dict[str, dict] = Field(
        default_factory=dict, description="Mapping of question_id to state object"
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


class WebPreviewRequest(BaseModel):
    """Request body for /web/preview and /web/ingest."""

    url: str = Field(..., min_length=1, max_length=4096, description="URL to fetch")


class WebPreviewResponse(BaseModel):
    """Result of fetching a URL without committing chunks."""

    initial_url: str = Field(..., description="URL the user submitted")
    final_url: str = Field(..., description="URL after redirects")
    hostname: str = Field(..., description="Hostname of the final URL")
    title: str | None = Field(default=None, description="Page title (HTML only)")
    content_type: str = Field(..., description="Response Content-Type, lowercased")
    extracted_chars: int = Field(..., description="Length of extracted text")
    preview_text: str = Field(..., description="First 500 characters of extracted text")
    warnings: list[str] = Field(default_factory=list, description="Warning flags")
    already_ingested_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of a prior ingest of this URL in the session.",
    )
    source_label: str = Field(..., description="Display label derived for the source")


class WebIngestResponse(BaseModel):
    """Result of ingesting a previously-previewed URL."""

    status: str = Field(default="success")
    source: str = Field(..., description="Collection / source name written")
    source_url: str = Field(..., description="Canonical URL after redirect resolution")


class WebConsentRequest(BaseModel):
    """Request body for PUT /session/web-consent."""

    enabled: bool = Field(..., description="Grant or revoke web-source consent for the session")


class WebConsentResponse(BaseModel):
    """Response carrying the current web-consent flag."""

    web_consent: bool


class SessionListItem(BaseModel):
    """Summary of a user session."""

    session_id: str
    created_at: str
    expires_at: str
    remaining_hours: float
    has_survey: bool = False


class SessionListResponse(BaseModel):
    """List of user sessions."""

    sessions: list[SessionListItem] = Field(default_factory=list)


class TransferRequest(BaseModel):
    """Request to transfer a session to another user."""

    recipient_user_id: str = Field(max_length=200)


# ---------------------------------------------------------------------------
# Batch suggest endpoint helpers
# ---------------------------------------------------------------------------


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
    return [BatchSuggestSection(id="_implicit", title=None, items=request.items or [])]
