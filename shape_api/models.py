"""Pydantic request/response models for the Shape API."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
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


class SectionPatch(BaseModel):
    """Partial update for a section. Only set fields are applied.

    `questions` is deliberately absent: question membership is managed via the
    add/update/delete-question operations, not by patching a section.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class QuestionPatch(BaseModel):
    """Partial update for a question. Only set fields are applied."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    type: QuestionType | None = None
    answer_options: list[AnswerOption] | None = None
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    required: bool | None = None
    metadata: dict[str, Any] | None = None


class AddSectionRequest(BaseModel):
    """Body for POST /chat/{session_id}/survey/sections."""

    section: Section
    after_id: str | None = None


class AddQuestionRequest(BaseModel):
    """Body for POST /chat/{session_id}/survey/sections/{section_id}/questions."""

    question: Question
    after_id: str | None = None


class MoveQuestionRequest(BaseModel):
    """Body for PATCH /chat/{session_id}/survey/questions/{question_id}/position.

    `after_id` omitted moves to the front of the target section; `section_id`
    moves the question into a different section, preserving its id.
    """

    after_id: str | None = None
    section_id: str | None = None


class MoveSectionRequest(BaseModel):
    """Body for PATCH /chat/{session_id}/survey/sections/{section_id}/position."""

    after_id: str | None = None


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
