"""Shape UI: chat, survey preview, content upload, export, and session management routes."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from shape_ui import api_client
from shape_ui.api_client import APIError
from shape_ui.auth import get_token
from shape_ui.router import EXPORT_FORMATS, _render_error, templates

router = APIRouter()


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
    action: Annotated[str, Form()] = "download",
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
                    "session_id": session_id,
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
                    "session_id": session_id,
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

    if request.headers.get("HX-Request") == "true":
        current_url = request.headers.get("HX-Current-URL", "")
        if "/chat" in current_url:
            return Response(headers={"HX-Redirect": "/"})
        return Response(status_code=200)
    return RedirectResponse(url="/", status_code=303)
