"""Cue UI: landing page, session list, and survey upload routes."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from cue_ui import api_client
from cue_ui.api_client import APIError
from cue_ui.auth import get_token, set_token_cookie
from cue_ui.router import SURVEY_FORMATS, templates

router = APIRouter()

_API_FORMATS = ["lss", "qsf"]


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing: redirect to session list (or login)."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    return RedirectResponse(url="/sessions", status_code=302)


@router.get("/sessions", response_class=HTMLResponse)
async def session_list_page(request: Request):
    """Show the user's active sessions."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        sessions = await api_client.list_sessions(token)
    except Exception:  # noqa: S110
        sessions = []
    return templates.TemplateResponse(request, "sessions.html", {"sessions": sessions})


@router.post("/sessions/new")
async def ui_create_session(request: Request):
    """Create a new session and redirect to the upload page."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        result = await api_client.create_new_session(token)
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "sessions.html",
            {"sessions": [], "error": exc.detail},
            status_code=exc.status_code,
        )
    response = RedirectResponse(url="/upload", status_code=302)
    set_token_cookie(response, result["token"])
    return response


@router.post("/sessions/{session_id}/select")
async def ui_select_session(request: Request, session_id: str):
    """Resume a session and redirect to review."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        result = await api_client.select_session(token, session_id)
    except APIError:
        return RedirectResponse(url="/sessions", status_code=302)
    response = RedirectResponse(url=f"/session/{session_id}/review", status_code=302)
    set_token_cookie(response, result["token"])
    return response


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Survey upload page."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "upload.html",
        {"formats": SURVEY_FORMATS},
    )


@router.post("/upload")
async def upload_survey(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    format: Annotated[str, Form(...)],
):
    """Import a survey file and redirect to document upload step."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    if format not in SURVEY_FORMATS:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "formats": SURVEY_FORMATS,
                "error": f"Unsupported format '{format}'. Supported: {', '.join(SURVEY_FORMATS).upper()}",
            },
            status_code=400,
        )

    file_bytes = await file.read()
    try:
        survey_id, warning = await api_client.import_survey_file(
            token=token,
            file_bytes=file_bytes,
            filename=file.filename or "survey",
            format=format,
        )
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "formats": SURVEY_FORMATS,
                "error": f"Could not import survey: {exc.detail}",
            },
            status_code=exc.status_code,
        )

    redirect_url = f"/session/{survey_id}/documents"
    if warning:
        from urllib.parse import urlencode

        redirect_url += "?" + urlencode({"warning": warning})
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/upload-from-api")
async def upload_survey_from_api(
    request: Request,
    format: Annotated[str, Form()],
    survey_id: Annotated[str, Form()],
    api_url: str = Form(default=""),
    api_token: str = Form(default=""),
    datacenter_id: str = Form(default=""),
    username: str = Form(default=""),
    password: str = Form(default=""),
):
    """Import a survey directly from the platform API and redirect to document upload."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    if format not in _API_FORMATS:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "formats": SURVEY_FORMATS,
                "api_error": f"Unsupported format '{format}'. Choose one of: {', '.join(_API_FORMATS)}.",
                "api_form": {
                    "format": format,
                    "survey_id": survey_id,
                    "api_url": api_url,
                    "datacenter_id": datacenter_id,
                    "username": username,
                },
            },
            status_code=400,
        )

    try:
        result_id, warning = await api_client.import_survey_from_api(
            token=token,
            format=format,
            survey_id=survey_id,
            api_url=api_url or None,
            api_token=api_token or None,
            datacenter_id=datacenter_id or None,
            username=username or None,
            password=password or None,
        )
    except APIError as exc:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "formats": SURVEY_FORMATS,
                "api_error": exc.detail,
                "api_form": {
                    "format": format,
                    "survey_id": survey_id,
                    "api_url": api_url,
                    "datacenter_id": datacenter_id,
                    "username": username,
                },
            },
            status_code=exc.status_code,
        )

    redirect_url = f"/session/{result_id}/documents"
    if warning:
        from urllib.parse import urlencode

        redirect_url += "?" + urlencode({"warning": warning})
    return RedirectResponse(url=redirect_url, status_code=302)
