"""All routes for the M-Chat UI survey authoring frontend."""

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from m_chat_ui import api_client
from m_chat_ui.api_client import APIError
from m_chat_ui.auth import (
    MCHAT_API_URL,
    MCHAT_PUBLIC_URL,
    clear_token_cookie,
    get_token,
    set_token_cookie,
)

router = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Adapter capabilities: which platforms support push-to-API vs download-only
ADAPTER_CAPABILITIES = {
    "lss": {"label": "LimeSurvey", "push": True},
    "limesurvey": {"label": "LimeSurvey", "push": True},
    "qsf": {"label": "Qualtrics", "push": True},
    "qualtrics": {"label": "Qualtrics", "push": True},
    "sm": {"label": "SurveyMonkey", "push": False},
    "surveymonkey": {"label": "SurveyMonkey", "push": False},
    "qti": {"label": "QTI", "push": False},
}

EXPORT_FORMATS = [
    {"id": "lss", "label": "LimeSurvey", "push": True},
    {"id": "qsf", "label": "Qualtrics", "push": True},
    {"id": "sm", "label": "SurveyMonkey", "push": False},
    {"id": "qti", "label": "QTI", "push": False},
]


def _render_error(request: Request, message: str, status_code: int = 500) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": message},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@router.get("/auth/login")
async def auth_login():
    """Redirect browser to M-Chat OIDC login (public URL, browser-accessible)."""
    return RedirectResponse(url=f"{MCHAT_PUBLIC_URL}/auth/login")


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    token: str | None = None,
):
    """Handle OIDC callback: proxy code+state to M-Chat server-side, set cookie."""
    if token:
        # Direct token handoff (e.g. dev/manual flow)
        response = RedirectResponse(url="/", status_code=302)
        set_token_cookie(response, token)
        return response

    if code and state:
        # OIDC authorization code flow: forward to m-chat server-side
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{MCHAT_API_URL}/auth/callback",
                    params={"code": code, "state": state},
                    follow_redirects=False,
                )
            resp.raise_for_status()
            jwt_token = resp.json().get("token")
        except Exception:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"message": "Authentication failed: could not exchange code for token."},
                status_code=502,
            )
        if not jwt_token:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"message": "Authentication failed: no token in response."},
                status_code=502,
            )
        response = RedirectResponse(url="/", status_code=302)
        set_token_cookie(response, jwt_token)
        return response

    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": "Authentication failed: no token or authorization code received."},
        status_code=400,
    )


@router.get("/auth/logout")
async def auth_logout():
    """Clear auth cookie and redirect to login."""
    response = RedirectResponse(url="/auth/login", status_code=302)
    clear_token_cookie(response)
    return response


# ---------------------------------------------------------------------------
# Landing: session list
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page: list sessions + Start new survey."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    sessions = []
    error = None
    try:
        sessions = await api_client.list_sessions(token)
    except APIError as exc:
        error = f"Could not load sessions: {exc.detail}"

    return templates.TemplateResponse(
        request,
        "index.html",
        {"sessions": sessions, "error": error},
    )


@router.post("/sessions")
async def create_session(request: Request):
    """Create a new chat session and redirect to setup."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        session = await api_client.create_session(token)
    except APIError as exc:
        return _render_error(request, f"Could not create session: {exc.detail}", exc.status_code)

    session_id = session["session_id"]
    return RedirectResponse(url=f"/session/{session_id}/setup", status_code=302)


# ---------------------------------------------------------------------------
# Setup: style configuration
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/setup", response_class=HTMLResponse)
async def setup_page(request: Request, session_id: str):
    """Style setup: language, free-text description, style doc upload."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        style = await api_client.get_style(token, session_id)
    except APIError as exc:
        if exc.status_code == 403:
            return _render_error(request, "Session not found or access denied.", 403)
        return _render_error(request, f"Could not load style: {exc.detail}", exc.status_code)

    return templates.TemplateResponse(
        request,
        "setup.html",
        {"session_id": session_id, "style": style},
    )


@router.post("/session/{session_id}/setup")
async def setup_submit(
    request: Request,
    session_id: str,
    language: Annotated[str | None, Form()] = None,
    free_text: Annotated[str | None, Form()] = None,
):
    """Save style settings and redirect to chat."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        await api_client.update_style(token, session_id, language or None, free_text or None)
    except APIError as exc:
        return _render_error(request, f"Could not save style: {exc.detail}", exc.status_code)

    return RedirectResponse(url=f"/session/{session_id}/chat", status_code=302)


@router.post("/session/{session_id}/setup/style-doc", response_class=HTMLResponse)
async def upload_style_doc(
    request: Request,
    session_id: str,
    file: Annotated[UploadFile, File(...)],
):
    """HTMX: upload style guide document, return inline summary partial."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    file_bytes = await file.read()
    try:
        result = await api_client.upload_style_doc(
            token, session_id, file_bytes, file.filename or "style_doc"
        )
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "partials/style_doc_summary.html",
            {"error": exc.detail},
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "partials/style_doc_summary.html",
        {
            "filename": result.get("filename", file.filename),
            "topic_summary": result.get("topic_summary", ""),
            "characters_extracted": result.get("characters_extracted", 0),
        },
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/chat", response_class=HTMLResponse)
async def chat_page(request: Request, session_id: str):
    """Main chat interface: messages + survey sidebar."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        session = await api_client.get_session(token, session_id)
        style = await api_client.get_style(token, session_id)
        survey = await api_client.get_survey(token, session_id)
        messages = await api_client.get_messages(token, session_id)
    except APIError as exc:
        if exc.status_code == 403:
            return _render_error(request, "Session not found or access denied.", 403)
        return _render_error(request, f"Could not load chat: {exc.detail}", exc.status_code)

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "session_id": session_id,
            "session": session,
            "style": style,
            "survey": survey,
            "messages": messages,
        },
    )


@router.post("/session/{session_id}/chat", response_class=HTMLResponse)
async def chat_send(
    request: Request,
    session_id: str,
    message: Annotated[str, Form(...)],
):
    """HTMX: send message, return message partial (+ updated survey if changed)."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    try:
        result = await api_client.send_message(token, session_id, message)
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "partials/message.html",
            {"user_message": message, "error": exc.detail},
            status_code=exc.status_code,
        )

    survey = None
    if result.get("survey_updated"):
        try:
            survey = await api_client.get_survey(token, session_id)
        except APIError:
            pass

    return templates.TemplateResponse(
        request,
        "partials/message.html",
        {
            "user_message": message,
            "assistant_message": result.get("message", ""),
            "survey_updated": result.get("survey_updated", False),
            "survey": survey,
            "session_id": session_id,
        },
    )


@router.get("/session/{session_id}/survey-preview", response_class=HTMLResponse)
async def survey_preview_partial(request: Request, session_id: str):
    """HTMX: return current survey preview partial (polled after survey_updated)."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    survey = None
    try:
        survey = await api_client.get_survey(token, session_id)
    except APIError:
        pass

    return templates.TemplateResponse(
        request,
        "partials/survey_preview.html",
        {"survey": survey},
    )


@router.post("/session/{session_id}/upload", response_class=HTMLResponse)
async def upload_content_doc(
    request: Request,
    session_id: str,
    file: Annotated[UploadFile, File(...)],
):
    """HTMX: upload content document, return upload summary partial."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    file_bytes = await file.read()
    try:
        result = await api_client.upload_content_doc(
            token, session_id, file_bytes, file.filename or "document"
        )
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "partials/upload_summary.html",
            {"error": exc.detail},
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "partials/upload_summary.html",
        {
            "filename": result.get("filename", file.filename),
            "topic_summary": result.get("topic_summary", ""),
            "characters_extracted": result.get("characters_extracted", 0),
        },
    )


# ---------------------------------------------------------------------------
# Export / Publish
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/export", response_class=HTMLResponse)
async def export_page(request: Request, session_id: str):
    """Export / publish page: platform selector."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    survey = None
    survey_error = None
    try:
        survey = await api_client.get_survey(token, session_id)
    except APIError as exc:
        survey_error = f"Could not load survey draft: {exc.detail} (status {exc.status_code})"

    return templates.TemplateResponse(
        request,
        "export.html",
        {
            "session_id": session_id,
            "survey": survey,
            "survey_error": survey_error,
            "formats": EXPORT_FORMATS,
        },
    )


@router.post("/session/{session_id}/export", response_class=HTMLResponse)
async def export_submit(
    request: Request,
    session_id: str,
    fmt: Annotated[str, Form(...)],
    action: Annotated[str, Form(...)] = "download",
    api_url: Annotated[str | None, Form()] = None,
    platform_token: Annotated[str | None, Form()] = None,
    username: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
):
    """HTMX: export or push survey, return result fragment."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    try:
        if action == "push":
            result = await api_client.create_survey_on_platform(
                token,
                session_id,
                fmt,
                api_url=api_url or None,
                platform_token=platform_token or None,
                username=username or None,
                password=password or None,
            )
            return templates.TemplateResponse(
                request,
                "partials/export_result.html",
                {
                    "action": "push",
                    "fmt": fmt,
                    "result": result,
                    "platform_id": result.get("platform_id"),
                    "created_via": result.get("created_via"),
                },
            )
        else:
            result = await api_client.export_survey(token, session_id, fmt)
            return templates.TemplateResponse(
                request,
                "partials/export_result.html",
                {
                    "action": "download",
                    "fmt": fmt,
                    "content": result.get("content", ""),
                    "filename": f"survey.{fmt}",
                },
            )
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "partials/export_result.html",
            {"error": exc.detail},
            status_code=exc.status_code,
        )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


@router.post("/session/{session_id}/reset")
async def reset_session(request: Request, session_id: str):
    """Reset draft survey and vocabulary, keep conversation."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        await api_client.reset_session(token, session_id)
    except APIError as exc:
        return _render_error(request, f"Could not reset session: {exc.detail}", exc.status_code)

    return RedirectResponse(url=f"/session/{session_id}/chat", status_code=302)


@router.delete("/session/{session_id}")
async def delete_session(request: Request, session_id: str):
    """Delete a session and redirect to home."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        await api_client.delete_session(token, session_id)
    except APIError as exc:
        return _render_error(request, f"Could not delete session: {exc.detail}", exc.status_code)

    # HTMX requests: return empty body so the card is removed from the DOM.
    # Regular requests (e.g. form submit): redirect to home.
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse("")
    return RedirectResponse(url="/", status_code=302)
