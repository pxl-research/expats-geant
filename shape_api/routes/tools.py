"""Shape API: AI tool routes (suggest, validate, tag)."""

from fastapi import APIRouter, HTTPException, Request, status

from m_shared.models.question import Question
from m_shared.models.survey import Survey
from m_shared.rate_limit import limiter
from m_shared.session.manager import SessionManager
from shape_api.models import (
    SuggestRequest,
    SuggestResponse,
    TagRequest,
    TagResponse,
    ValidateRequest,
    ValidateResponse,
)
from shape_api.session import (
    load_draft_survey,
    load_style_profile,
    load_tag_vocabulary,
    save_tag_vocabulary,
    update_vocabulary,
)
from shape_api.suggestion_engine import suggest_question
from shape_api.tagging_engine import suggest_tags
from shape_api.validation_engine import validate_question, validate_survey

router = APIRouter()


def _get_chat_session_context(
    session_id: str,
    user_id: str,
    session_manager: SessionManager,
) -> dict | None:
    """Load chat session context (style profile, vocab, draft survey).

    Returns:
        dict with style_profile, vocabulary, draft_survey keys, or None if
        session not found or belongs to a different user.
    """
    session = session_manager.get_session(session_id)
    if session is None or session.user_id != user_id:
        return None
    base_path = str(session_manager.base_path)
    return {
        "style_profile": load_style_profile(base_path, session_id),
        "vocabulary": load_tag_vocabulary(base_path, session_id),
        "draft_survey": load_draft_survey(base_path, session_id),
    }


@router.post("/suggest", response_model=SuggestResponse)
@limiter.limit("10/minute")
async def suggest_endpoint(request: Request, body: SuggestRequest):
    """Generate improved phrasings for a survey question."""
    llm_client = getattr(request.state, "llm_client", None) or request.app.state.llm_client
    session_manager = request.app.state.session_manager

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


@router.post("/validate", response_model=ValidateResponse)
@limiter.limit("10/minute")
async def validate_endpoint(request: Request, body: ValidateRequest):
    """Validate a question or full survey for quality issues."""
    llm_client = getattr(request.state, "llm_client", None) or request.app.state.llm_client
    session_manager = request.app.state.session_manager

    claims = request.state.claims
    user_id = claims.get("user_id")

    style_profile = None
    session_draft = None
    if body.session_id:
        ctx = _get_chat_session_context(body.session_id, user_id, session_manager)
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chat session not found or access denied",
            )
        style_profile = ctx["style_profile"]
        session_draft = ctx.get("draft_survey")

    if body.question is None and body.survey is None and session_draft is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'question' or 'survey' must be provided, or a session_id with an existing draft",
        )

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
    elif session_draft is not None:
        raw_issues = validate_survey(
            survey=session_draft,
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


@router.post("/tag", response_model=TagResponse)
@limiter.limit("10/minute")
async def tag_endpoint(request: Request, body: TagRequest):
    """Suggest normalised tags for a survey question."""
    llm_client = getattr(request.state, "llm_client", None) or request.app.state.llm_client
    session_manager = request.app.state.session_manager

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
