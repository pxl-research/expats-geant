"""Pydantic request/response models for the Shape API."""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Stateless endpoints
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    format: str = Field(max_length=50)  # "limesurvey" | "qualtrics" | "surveymonkey" | "qti"
    content: str = Field(max_length=10_000_000)  # raw file content (10 MB limit)


class ImportResponse(BaseModel):
    survey: dict  # Survey serialised as JSON


class ExportRequest(BaseModel):
    format: str = Field(max_length=50)
    survey: dict


class ExportResponse(BaseModel):
    format: str
    content: str  # platform file content


class CreateRequest(BaseModel):
    format: str = Field(max_length=50)
    survey: dict
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
    question: dict
    session_id: str | None = None
    n_suggestions: int = Field(default=3, ge=1, le=5)


class SuggestResponse(BaseModel):
    suggestions: list[dict]  # [{"phrasing": "...", "reasoning": "..."}]


class ValidateRequest(BaseModel):
    question: dict | None = None
    survey: dict | None = None
    session_id: str | None = None


class ValidateResponse(BaseModel):
    issues: list[dict]  # [{"question_id","severity","code","message"}]


class TagRequest(BaseModel):
    question: dict
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
    style_profile: dict


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class ChatTurnRequest(BaseModel):
    message: str = Field(max_length=50_000)


class ChatTurnResponse(BaseModel):
    message: str
    survey_updated: bool


class ChatSurveyResponse(BaseModel):
    survey: dict | None


class SurveyUpdateRequest(BaseModel):
    survey: dict


class SurveyUpdateResponse(BaseModel):
    status: str
    validation_issues: list[dict]


class StyleUpdateRequest(BaseModel):
    language: str | None = Field(default=None, max_length=100)
    free_text: str | None = Field(default=None, max_length=5000)


class StyleProfileResponse(BaseModel):
    session_id: str
    style_profile: dict


class DocumentUploadResponse(BaseModel):
    filename: str
    topic_summary: str
    characters_extracted: int
