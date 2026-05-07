"""Cue UI: document upload, review, suggestion stream, submit, and session routes."""

import json
import logging

import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from cue_ui import api_client
from cue_ui.api_client import APIError, auth_headers
from cue_ui.auth import CUE_API_URL, get_token
from cue_ui.router import _render_error, templates

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.post("/session/{session_id}/upload-doc")
async def upload_single_doc(request: Request, session_id: str, file: UploadFile = File(...)):
    """Upload a single document (called via fetch from documents.js)."""
    token = get_token(request)
    if not token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    file_bytes = await file.read()
    try:
        await api_client.ingest_document(
            token=token,
            session_id=session_id,
            file_bytes=file_bytes,
            filename=file.filename or "upload",
        )
    except APIError as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"status": "ok"})


@router.post("/session/{session_id}/upload-text-snippet")
async def upload_text_snippet(request: Request, session_id: str):
    """Upload a text snippet (called via fetch from documents.js)."""
    token = get_token(request)
    if not token:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid or missing JSON body"}, status_code=400)
    text = body.get("text", "").strip()
    label = body.get("label") or None
    if not text:
        return JSONResponse({"error": "Empty text"}, status_code=400)
    try:
        await api_client.ingest_text_snippet(
            token=token,
            session_id=session_id,
            text=text,
            label=label,
        )
    except APIError as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"status": "ok"})


@router.post("/session/{session_id}/documents")
async def documents_upload(
    request: Request,
    session_id: str,
    files: list[UploadFile] | None = File(default=None),
    text: str = Form(default=""),
    text_label: str = Form(default=""),
):
    """Forward each uploaded document and/or text snippet to Cue ingestion API."""
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

    survey_format = survey.get("metadata", {}).get("format", "")
    capabilities: set[str] = set()
    if survey_format:
        try:
            capabilities = await api_client.get_capabilities(token=token, format=survey_format)
        except APIError:
            pass

    can_submit = "submit" in capabilities

    # Fetch document info for the session panel
    documents = []
    try:
        stats = await api_client.get_session_stats(token)
        documents = stats.get("documents", [])
    except APIError:
        pass

    # Fetch server-side review state (best-effort; falls back to localStorage)
    review_state = {}
    try:
        review_state = await api_client.get_review_state(token)
    except Exception:  # noqa: S110
        pass

    # Fetch cached suggestions (skip SSE regeneration on reload)
    cached_suggestions = {}
    try:
        cached_suggestions = await api_client.get_cached_suggestions(token)
    except Exception:  # noqa: S110
        pass

    return templates.TemplateResponse(
        request,
        "survey.html",
        {
            "session_id": session_id,
            "survey": survey,
            "can_submit": can_submit,
            "form_values": {},
            "documents": documents,
            "review_state": review_state,
            "cached_suggestions": cached_suggestions,
        },
    )


# ---------------------------------------------------------------------------
# Suggestion stream (SSE proxy)
# ---------------------------------------------------------------------------


def _survey_to_batch_items(survey: dict) -> list[dict]:
    """Convert a stored survey dict to BatchSuggestItem list."""
    items = []
    for section in survey.get("sections", []):
        for q in section.get("questions", []):
            opts = q.get("answer_options", [])
            q_type = q["type"]
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

    # Skip questions that already have cached suggestions
    try:
        cached = await api_client.get_cached_suggestions(token)
    except Exception:  # noqa: S110
        cached = {}
    if cached:
        items = [item for item in items if item["id"] not in cached]

    if not items:

        async def all_cached_generator():
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            all_cached_generator(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    body = {"assessment_id": session_id, "items": items}

    async def proxy_generator():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{CUE_API_URL}/suggest/stream",
                    json=body,
                    headers=auth_headers(token),
                    timeout=None,
                ) as resp:
                    if resp.status_code >= 400:
                        logger.error("Autofill API returned %s", resp.status_code)
                        yield f'event: error\ndata: {{"detail": "Autofill service error ({resp.status_code})"}}\n\n'
                        return
                    content_type = resp.headers.get("content-type", "")
                    if "text/event-stream" not in content_type:
                        logger.error("Unexpected content-type from autofill API: %s", content_type)
                        yield 'event: error\ndata: {"detail": "Autofill service returned an unexpected response."}\n\n'
                        return
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
# Answer report, submit, delete session
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
    """Delete the current session (called via fetch from cleanup modal)."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        await api_client.delete_session(token)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"status": "deleted"}, status_code=200)


# ---------------------------------------------------------------------------
# Review state proxy (UI → Cue API)
# ---------------------------------------------------------------------------


@router.put("/session/{session_id}/review-state/{question_id}")
async def save_review_state(request: Request, session_id: str, question_id: str):
    """Proxy review state save to the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
    try:
        await api_client.save_review_state(token, question_id, body)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"status": "ok"})


@router.get("/session/{session_id}/review-state")
async def get_review_state(request: Request, session_id: str):
    """Proxy review state load from the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        states = await api_client.get_review_state(token)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(states)
