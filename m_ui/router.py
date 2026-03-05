"""All routes for the M-UI survey review frontend."""

import os
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from m_ui import api_client
from m_ui.api_client import APIError
from m_ui.auth import (
    AUTOFILL_API_URL,
    clear_token_cookie,
    get_token,
    set_token_cookie,
)

router = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Supported survey file formats presented to the user
SURVEY_FORMATS = ["qsf", "lss", "qti"]


def _render_error(request: Request, message: str, status_code: int = 500) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": message},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@router.get("/auth/login")
async def auth_login():
    """Redirect to M-Autofill OIDC login."""
    return RedirectResponse(url=f"{AUTOFILL_API_URL}/auth/login")


@router.get("/auth/callback")
async def auth_callback(request: Request, token: str | None = None):
    """Receive token from M-Autofill callback, set cookie, redirect to /."""
    if not token:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "Authentication failed: no token received."},
            status_code=400,
        )
    response = RedirectResponse(url="/", status_code=302)
    set_token_cookie(response, token)
    return response


@router.get("/auth/logout")
async def auth_logout():
    """Clear auth cookie and redirect to login."""
    response = RedirectResponse(url="/auth/login", status_code=302)
    clear_token_cookie(response)
    return response


# ---------------------------------------------------------------------------
# Landing / upload
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page: enter survey ID or upload file."""
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
        survey_id = await api_client.import_survey_file(
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

    return RedirectResponse(url=f"/session/{survey_id}/documents", status_code=302)


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/documents", response_class=HTMLResponse)
async def documents_page(request: Request, session_id: str):
    """Render optional document upload step."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "documents.html",
        {"session_id": session_id},
    )


@router.post("/session/{session_id}/documents")
async def documents_upload(
    request: Request,
    session_id: str,
    files: Annotated[list[UploadFile], File(...)],
):
    """Forward each uploaded document to M-Autofill ingestion API."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    file_errors: list[dict] = []
    for upload in files:
        if not upload.filename:
            continue
        file_bytes = await upload.read()
        try:
            await api_client.ingest_document(
                token=token,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=upload.filename,
            )
        except APIError as exc:
            file_errors.append({"filename": upload.filename, "error": exc.detail})

    if file_errors:
        return templates.TemplateResponse(
            request,
            "documents.html",
            {
                "session_id": session_id,
                "file_errors": file_errors,
            },
            status_code=422,
        )

    return RedirectResponse(url=f"/session/{session_id}/review", status_code=302)


# ---------------------------------------------------------------------------
# Review page
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/review", response_class=HTMLResponse)
async def review_page(request: Request, session_id: str):
    """Load survey + capabilities, render survey.html."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    try:
        survey = await api_client.get_survey(token=token, survey_id=session_id)
    except APIError as exc:
        if exc.status_code in (404, 410):
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "message": "Your session has expired. Please start a new session.",
                    "session_expired": True,
                },
                status_code=410,
            )
        return _render_error(request, f"Could not load survey: {exc.detail}", exc.status_code)

    # Determine capabilities (display-only vs submit)
    survey_format = survey.get("metadata", {}).get("format", "")
    capabilities: set[str] = set()
    if survey_format:
        try:
            capabilities = await api_client.get_capabilities(token=token, format=survey_format)
        except APIError:
            pass  # Fall back to display-only

    can_submit = "submit" in capabilities

    return templates.TemplateResponse(
        request,
        "survey.html",
        {
            "session_id": session_id,
            "survey": survey,
            "can_submit": can_submit,
            "form_values": {},
        },
    )


# ---------------------------------------------------------------------------
# HTMX suggestion partial
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/suggest", response_class=HTMLResponse)
async def suggest_partial(request: Request, session_id: str):
    """HTMX endpoint: fetch and return suggestion_block.html partial."""
    token = get_token(request)
    if not token:
        return HTMLResponse("<p>Not authenticated.</p>", status_code=401)

    try:
        suggestions = await api_client.batch_suggest(
            token=token, session_id=session_id, survey_id=session_id
        )
    except APIError as exc:
        return HTMLResponse(
            f"<p class='error'>Could not load suggestions: {exc.detail}</p>",
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "partials/suggestion_block.html",
        {"session_id": session_id, "suggestions": suggestions},
    )


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


@router.post("/session/{session_id}/submit")
async def submit_responses(request: Request, session_id: str):
    """Collect form data, call submit API, redirect to submitted.html or show error."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    form = await request.form()
    responses = {k: v for k, v in form.items() if not k.startswith("_")}

    try:
        await api_client.submit_responses(token=token, session_id=session_id, responses=responses)
    except APIError as exc:
        # Re-render survey with error, preserving form values
        try:
            survey = await api_client.get_survey(token=token, survey_id=session_id)
        except APIError:
            survey = {}
        return templates.TemplateResponse(
            request,
            "survey.html",
            {
                "session_id": session_id,
                "survey": survey,
                "can_submit": True,
                "submit_error": exc.detail,
                "form_values": dict(responses),
            },
            status_code=exc.status_code,
        )

    return templates.TemplateResponse(
        request,
        "submitted.html",
        {"session_id": session_id},
    )
