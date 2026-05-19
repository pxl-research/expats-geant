"""Shape UI: landing page, session creation, and style setup routes."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from shape_ui import api_client
from shape_ui.api_client import APIError
from shape_ui.auth import get_token, set_token_cookie
from shape_ui.router import _render_error, templates

router = APIRouter()


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
    response = RedirectResponse(url=f"/session/{session_id}/setup", status_code=302)
    if session.get("token"):
        set_token_cookie(response, session["token"])
    return response


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
