"""Pydantic request/response models for the Shape API."""

from pydantic import BaseModel, Field

from m_shared.models.question import Question
from m_shared.models.survey import Survey
from shape_api.suggestion_engine import SuggestionResult
from shape_api.validation_engine import ValidationIssue

# ---------------------------------------------------------------------------
# Shared nested shapes
# ---------------------------------------------------------------------------


class StyleProfile(BaseModel):
    """Session-level style guidance applied to LLM-assisted edits."""

    language: str = Field(default="en", max_length=100)
    free_text: str = Field(default="", max_length=5000)
    document_summary: str = Field(default="", max_length=10_000)
    defaults_applied: bool = True


class MessageItem(BaseModel):
    """A single conversational message exchanged with the assistant."""

    role: str
    content: str


# ---------------------------------------------------------------------------
# Stateless endpoints
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    format: str = Field(max_length=50)  # "limesurvey" | "qualtrics" | "surveymonkey" | "qti"
    content: str = Field(max_length=10_000_000)  # raw file content (10 MB limit)


class ImportResponse(BaseModel):
    survey: Survey


class ExportRequest(BaseModel):
    format: str = Field(max_length=50)
    survey: Survey


class ExportResponse(BaseModel):
    format: str
    content: str  # platform file content


class CreateRequest(BaseModel):
    format: str = Field(max_length=50)
    survey: Survey
    # Optional adapter credentials (server falls back to file export if absent)
    api_url: str | None = Field(default=None, max_length=2000)
    token: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=200)


class CreateResponse(BaseModel):
    format: str
    platform_id: str  # platform survey ID or file content
    created_via: str  # "api" | "file_export"


# ---------------------------------------------------------------------------
# Tool endpoints
# ---------------------------------------------------------------------------


class SuggestRequest(BaseModel):
    question: Question
    session_id: str | None = None
    n_suggestions: int = Field(default=3, ge=1, le=5)


class SuggestResponse(BaseModel):
    suggestions: list[SuggestionResult]


class ValidateRequest(BaseModel):
    question: Question | None = None
    survey: Survey | None = None
    session_id: str | None = None


class ValidateResponse(BaseModel):
    issues: list[ValidationIssue]


class TagRequest(BaseModel):
    question: Question
    session_id: str | None = None


class TagResponse(BaseModel):
    tags: list[str]
    vocabulary_updated: bool  # True if session vocabulary was updated


# ---------------------------------------------------------------------------
# Conversational API
# ---------------------------------------------------------------------------


class CreateChatSessionRequest(BaseModel):
    pass


class ChatSessionResponse(BaseModel):
    session_id: str
    user_id: str
    created_at: str  # ISO-8601
    expires_at: str  # ISO-8601
    style_profile: StyleProfile
    token: str | None = None


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class ChatTurnRequest(BaseModel):
    message: str = Field(max_length=50_000)


class ChatTurnResponse(BaseModel):
    message: str
    survey_updated: bool


class ChatSurveyResponse(BaseModel):
    survey: Survey | None


class ChatMessagesResponse(BaseModel):
    messages: list[MessageItem]


class DeleteSessionResponse(BaseModel):
    deleted: bool
    session_id: str


class ResetSessionResponse(BaseModel):
    reset: bool
    session_id: str
    cleared: list[str]


class SurveyUpdateRequest(BaseModel):
    survey: Survey


class SurveyUpdateResponse(BaseModel):
    status: str
    validation_issues: list[ValidationIssue]


class StyleUpdateRequest(BaseModel):
    language: str | None = Field(default=None, max_length=100)
    free_text: str | None = Field(default=None, max_length=5000)


class StyleProfileResponse(BaseModel):
    session_id: str
    style_profile: StyleProfile


class DocumentUploadResponse(BaseModel):
    filename: str
    topic_summary: str
    characters_extracted: int
