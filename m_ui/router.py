"""All routes for the M-UI survey review frontend."""

import json
import logging
import os
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from m_ui import api_client
from m_ui.api_client import APIError, _auth_headers
from m_ui.auth import (
    AUTOFILL_API_URL,
    AUTOFILL_PUBLIC_URL,
    clear_token_cookie,
    get_token,
    set_token_cookie,
)

logger = logging.getLogger(__name__)
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
    """Redirect browser to M-Autofill OIDC login (public URL, browser-accessible)."""
    return RedirectResponse(url=f"{AUTOFILL_PUBLIC_URL}/auth/login")


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    token: str | None = None,
):
    """Handle OIDC callback: proxy code+state to M-Autofill server-side, set cookie."""
    if token:
        # Direct token handoff (e.g. dev/manual flow)
        response = RedirectResponse(url="/", status_code=302)
        set_token_cookie(response, token)
        return response

    if code and state:
        # OIDC authorization code flow: forward to m-autofill server-side
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{AUTOFILL_API_URL}/auth/callback",
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


_API_FORMATS = ["lss", "qsf"]


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
                    # api_token and password intentionally omitted
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
                    # api_token and password intentionally omitted
                },
            },
            status_code=exc.status_code,
        )

    redirect_url = f"/session/{result_id}/documents"
    if warning:
        from urllib.parse import urlencode

        redirect_url += "?" + urlencode({"warning": warning})
    return RedirectResponse(url=redirect_url, status_code=302)


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/documents", response_class=HTMLResponse)
async def documents_page(request: Request, session_id: str, warning: str | None = None):
    """Render optional document upload step."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "documents.html",
        {"session_id": session_id, "warning": warning},
    )


@router.post("/session/{session_id}/documents")
async def documents_upload(
    request: Request,
    session_id: str,
    files: list[UploadFile] | None = File(default=None),
    text: str = Form(default=""),
    text_label: str = Form(default=""),
):
    """Forward each uploaded document and/or text snippet to M-Autofill ingestion API."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    has_text = bool(text.strip())

    if not files and not has_text:
        return RedirectResponse(url=f"/session/{session_id}/review", status_code=302)

    file_errors: list[dict] = []

    if files:
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

    if has_text:
        label = text_label.strip() or None
        try:
            await api_client.ingest_text_snippet(
                token=token,
                session_id=session_id,
                text=text,
                label=label,
            )
        except APIError as exc:
            file_errors.append({"filename": label or "pasted text", "error": exc.detail})

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


def _survey_to_batch_items(survey: dict) -> list[dict]:
    """Convert a stored survey dict to BatchSuggestItem list."""
    items = []
    for section in survey.get("sections", []):
        for q in section.get("questions", []):
            opts = q.get("answer_options", [])
            q_type = q["type"]
            # BatchSuggestItem requires choices to be non-empty for choice types;
            # fall back to open_ended if options are missing.
            if q_type in ("single_choice", "multiple_choice"):
                if opts:
                    choices = [{"id": o["id"], "label": o["text"]} for o in opts]
                else:
                    q_type = "open_ended"
                    choices = []
            else:
                choices = []
            items.append({"id": q["id"], "type": q_type, "prompt": q["text"], "choices": choices})
    return items


@router.get("/session/{session_id}/suggest-stream")
async def suggest_stream(session_id: str, request: Request):
    """SSE proxy: streams suggestion HTML blocks from the autofill API."""
    token = get_token(request)
    if not token:
        return HTMLResponse("Unauthorized", status_code=401)

    try:
        survey = await api_client.get_survey(token, session_id)
    except APIError as exc:
        return HTMLResponse(f"Error: {exc.detail}", status_code=exc.status_code)

    items = _survey_to_batch_items(survey)
    body = {"assessment_id": session_id, "items": items}

    async def proxy_generator():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{AUTOFILL_API_URL}/suggest/stream",
                    json=body,
                    headers=_auth_headers(token),
                    timeout=None,
                ) as resp:
                    event_type = None
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            event_type = line[len("event:") :].strip()
                        elif line.startswith("data:") and event_type == "suggestion":
                            data = json.loads(line[len("data:") :].strip())
                            html = templates.get_template("partials/suggestion_block.html").render(
                                sug=data
                            )
                            data_lines = "\n".join(f"data: {line}" for line in html.splitlines())
                            yield f"event: suggestion\n{data_lines}\n\n"
                            event_type = None
                        elif line.startswith("data:") and event_type == "done":
                            yield "event: done\ndata: {}\n\n"
                            return
                        elif line.startswith("data:") and event_type == "error":
                            yield f"event: error\ndata: {line[len('data:'):].strip()}\n\n"
                            return
        except Exception as e:
            logger.error("SSE proxy error: %s", e)
            yield 'event: error\ndata: {"message": "Suggestion stream failed."}\n\n'

    return StreamingResponse(
        proxy_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}/answer-report", response_class=HTMLResponse)
async def answer_report_page(request: Request, session_id: str):
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        await api_client.get_survey(token=token, survey_id=session_id)
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
        return _render_error(request, f"Could not validate session: {exc.detail}", exc.status_code)
    try:
        report = await api_client.fetch_answer_report(token=token)
    except APIError as exc:
        return _render_error(
            request, f"Could not load answer report: {exc.detail}", exc.status_code
        )
    return templates.TemplateResponse(
        request, "answer_report.html", {"session_id": session_id, "report": report}
    )


@router.get("/session/{session_id}/answer-report/download")
async def download_answer_report_proxy(request: Request, session_id: str):
    from fastapi.responses import JSONResponse

    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        await api_client.get_survey(token=token, survey_id=session_id)
    except APIError as exc:
        if exc.status_code in (404, 410):
            return _render_error(request, "Session not found or expired.", exc.status_code)
        return _render_error(request, f"Could not validate session: {exc.detail}", exc.status_code)
    try:
        report = await api_client.fetch_answer_report(token=token)
    except APIError as exc:
        return _render_error(request, exc.detail, exc.status_code)
    if report is None:
        return _render_error(request, "No answer report available yet.", 404)
    return JSONResponse(
        content=report,
        headers={"Content-Disposition": "attachment; filename=answer_report.json"},
    )


@router.post("/session/{session_id}/submit")
async def submit_responses(request: Request, session_id: str):
    """Collect form data, call submit API, redirect to submitted.html or show error."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    form = await request.form()
    # Collect all values per key; multi-value fields (multiple_choice checkboxes,
    # ranking hidden inputs) must not be collapsed to a single value.
    responses: dict[str, str | list[str]] = {}
    for k, v in form.multi_items():
        if k.startswith("_"):
            continue
        if k in responses:
            existing = responses[k]
            if isinstance(existing, list):
                existing.append(str(v))
            else:
                responses[k] = [str(existing), str(v)]
        else:
            responses[k] = str(v)

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


@router.delete("/session")
async def delete_session(request: Request):
    """Delete the current session and redirect to home."""
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)
    try:
        await api_client.delete_session(token)
    except APIError as exc:
        return _render_error(request, f"Could not delete session: {exc.detail}", exc.status_code)
    return RedirectResponse(url="/", status_code=302)
