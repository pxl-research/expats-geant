"""FastAPI application for M-Chat survey transform and tool endpoints."""

import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from m_chat.models import (
    CreateRequest,
    CreateResponse,
    ExportRequest,
    ExportResponse,
    ImportRequest,
    ImportResponse,
    SuggestRequest,
    SuggestResponse,
    TagRequest,
    TagResponse,
    ValidateRequest,
    ValidateResponse,
)
from m_chat.session import (
    load_draft_survey,
    load_style_profile,
    load_tag_vocabulary,
    save_tag_vocabulary,
    update_vocabulary,
)
from m_chat.suggestion_engine import suggest_question
from m_chat.tagging_engine import suggest_tags
from m_chat.validation_engine import validate_question, validate_survey
from m_shared.adapters.base import SurveyAdapter
from m_shared.adapters.registry import get_adapter
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.oauth import (
    OIDCConfigurationError,
    OIDCStateError,
    OIDCTokenError,
    exchange_code,
    get_authorization_url,
)
from m_shared.models.question import Question
from m_shared.models.survey import Survey
from m_shared.session.manager import SessionManager


def _get_adapter(
    fmt: str,
    api_url: str | None,
    token: str | None,
    username: str | None,
    password: str | None,
) -> SurveyAdapter:
    """Instantiate adapter for the given format with optional credentials.

    Args:
        fmt: Platform format identifier (e.g. "limesurvey", "qsf").
        api_url: API base URL or datacenter ID (format-specific meaning).
        token: API token (used for Qualtrics).
        username: Username (used for LimeSurvey).
        password: Password (used for LimeSurvey).

    Raises:
        HTTPException: 422 if format is not recognised.
    """
    try:
        if fmt in ("limesurvey", "lss"):
            return get_adapter(fmt, api_url=api_url, username=username, password=password)
        elif fmt in ("qualtrics", "qsf"):
            # api_url is used as datacenter_id for Qualtrics
            return get_adapter(fmt, api_token=token, datacenter_id=api_url)
        else:
            return get_adapter(fmt)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unknown format '{fmt}'. "
                "Supported: limesurvey, lss, qualtrics, qsf, qti, surveymonkey, sm."
            ),
        )


def _get_chat_session_context(
    session_id: str,
    user_id: str,
    session_manager: SessionManager,
) -> dict | None:
    """Load chat session context (style profile, vocab, draft survey).

    Verifies the session belongs to the requesting user.

    Returns:
        dict with style_profile, vocabulary, draft_survey keys, or None if
        session_id not found or belongs to a different user.
    """
    session = session_manager.get_session(session_id)
    if session is None:
        return None
    if session.user_id != user_id:
        return None
    base_path = str(session_manager.base_path)
    return {
        "style_profile": load_style_profile(base_path, session_id),
        "vocabulary": load_tag_vocabulary(base_path, session_id),
        "draft_survey": load_draft_survey(base_path, session_id),
    }


def create_app(
    session_manager: SessionManager,
    llm_client=None,
    adapter_registry=None,
) -> FastAPI:
    """Create the M-Chat FastAPI application.

    Args:
        session_manager: SessionManager for auth session handling.
        llm_client: Optional LLM client for tool endpoints (suggest, tag).
        adapter_registry: Unused; reserved for future extensibility.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="M-Chat API",
        description="Survey transform and AI tool endpoints",
        version="0.1.0",
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    @app.get("/")
    async def root():
        return {"service": "m-chat", "status": "running"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/dev/token", tags=["Development"])
    async def generate_dev_token(user_id: str = "dev_user", org: str = "dev_org"):
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token generation endpoint disabled in production",
            )
        session_id = f"dev_session_{user_id}"
        token = create_token(
            user_id=user_id,
            session_id=session_id,
            org=org,
            roles=["user"],
            expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")),
        )
        return {"token": token, "user_id": user_id}

    @app.get("/auth/login", tags=["Authentication"])
    async def auth_login():
        try:
            authorization_url, _state = await get_authorization_url()
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url=authorization_url, status_code=302)
        except OIDCConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OIDC not configured: {exc}",
            )

    @app.get("/auth/callback", tags=["Authentication"])
    async def auth_callback(code: str, state: str):
        try:
            platform_token = await exchange_code(code=code, state=state)
            return {"token": platform_token, "token_type": "bearer"}
        except OIDCStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OAuth state: {exc}",
            )
        except OIDCTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ID token validation failed: {exc}",
            )
        except OIDCConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OIDC not configured: {exc}",
            )

    # ------------------------------------------------------------------
    # Stateless transform endpoints (no auth required)
    # ------------------------------------------------------------------

    @app.post("/import", response_model=ImportResponse)
    async def import_survey(body: ImportRequest):
        """Parse a platform survey file and return the internal Survey JSON."""
        adapter = _get_adapter(body.format, None, None, None, None)
        try:
            survey = adapter.import_survey(body.content)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not parse survey: {exc}",
            )
        return ImportResponse(survey=survey.model_dump())

    @app.post("/export", response_model=ExportResponse)
    async def export_survey(body: ExportRequest):
        """Serialise an internal Survey to a platform-specific format."""
        adapter = _get_adapter(body.format, None, None, None, None)
        try:
            survey = Survey(**body.survey)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid survey payload: {exc}",
            )
        content = adapter.export_survey(survey)
        return ExportResponse(format=body.format, content=content)

    @app.post("/create", response_model=CreateResponse)
    async def create_survey_endpoint(body: CreateRequest):
        """Create a survey on the target platform or fall back to file export."""
        adapter = _get_adapter(body.format, body.api_url, body.token, body.username, body.password)
        try:
            survey = Survey(**body.survey)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid survey payload: {exc}",
            )

        credentials_present = any([body.api_url, body.token, body.username, body.password])

        if credentials_present and "create" in adapter.capabilities():
            try:
                content = adapter.create_survey(survey)
                created_via = "api"
            except (ValueError, NotImplementedError):
                content = adapter.export_survey(survey)
                created_via = "file_export"
        else:
            content = adapter.export_survey(survey)
            created_via = "file_export"

        return CreateResponse(format=body.format, platform_id=content, created_via=created_via)

    # ------------------------------------------------------------------
    # Context-aware tool endpoints (auth required)
    # ------------------------------------------------------------------

    @app.post("/suggest", response_model=SuggestResponse)
    async def suggest_endpoint(request: Request, body: SuggestRequest):
        """Generate improved phrasings for a survey question."""
        if llm_client is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM client not configured",
            )

        claims = request.state.claims
        user_id = claims.get("user_id")

        style_profile = None
        survey_context = None

        if body.session_id:
            ctx = _get_chat_session_context(body.session_id, user_id, session_manager)
            if ctx is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chat session not found or access denied",
                )
            style_profile = ctx["style_profile"]
            survey_context = ctx["draft_survey"]

        try:
            question = Question(**body.question)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid question payload: {exc}",
            )

        results = suggest_question(
            question=question,
            llm_client=llm_client,
            survey_context=survey_context,
            style_profile=style_profile,
            n_suggestions=body.n_suggestions,
        )
        suggestions = [{"phrasing": r.phrasing, "reasoning": r.reasoning} for r in results]
        return SuggestResponse(suggestions=suggestions)

    @app.post("/validate", response_model=ValidateResponse)
    async def validate_endpoint(request: Request, body: ValidateRequest):
        """Validate a question or full survey for quality issues."""
        if body.question is None and body.survey is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either 'question' or 'survey' must be provided",
            )

        claims = request.state.claims
        user_id = claims.get("user_id")

        style_profile = None
        if body.session_id:
            ctx = _get_chat_session_context(body.session_id, user_id, session_manager)
            if ctx is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chat session not found or access denied",
                )
            style_profile = ctx["style_profile"]

        issues = []
        if body.question is not None:
            try:
                question = Question(**body.question)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid question payload: {exc}",
                )
            raw_issues = validate_question(
                question=question,
                llm_client=llm_client,
                style_profile=style_profile,
            )
            issues = [
                {
                    "question_id": i.question_id,
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                }
                for i in raw_issues
            ]
        elif body.survey is not None:
            try:
                survey = Survey(**body.survey)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid survey payload: {exc}",
                )
            raw_issues = validate_survey(
                survey=survey,
                llm_client=llm_client,
                style_profile=style_profile,
            )
            issues = [
                {
                    "question_id": i.question_id,
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                }
                for i in raw_issues
            ]

        return ValidateResponse(issues=issues)

    @app.post("/tag", response_model=TagResponse)
    async def tag_endpoint(request: Request, body: TagRequest):
        """Suggest normalised tags for a survey question."""
        if llm_client is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM client not configured",
            )

        claims = request.state.claims
        user_id = claims.get("user_id")

        style_profile = None
        vocabulary = None
        session_ctx = None

        if body.session_id:
            session_ctx = _get_chat_session_context(body.session_id, user_id, session_manager)
            if session_ctx is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chat session not found or access denied",
                )
            style_profile = session_ctx["style_profile"]
            vocabulary = session_ctx["vocabulary"]

        try:
            question = Question(**body.question)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid question payload: {exc}",
            )

        tags = suggest_tags(
            question=question,
            llm_client=llm_client,
            vocabulary=vocabulary,
            style_profile=style_profile,
        )

        vocabulary_updated = False
        if body.session_id and session_ctx is not None:
            updated_vocab = update_vocabulary(
                vocab=session_ctx["vocabulary"],
                new_tags=tags,
                question_id=question.id,
            )
            save_tag_vocabulary(str(session_manager.base_path), body.session_id, updated_vocab)
            vocabulary_updated = True

        return TagResponse(tags=tags, vocabulary_updated=vocabulary_updated)

    return app
