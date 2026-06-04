"""Cue UI: document upload, review, suggestion stream, submit, and session routes."""

import json
import logging

import httpx
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from cue_ui import api_client
from cue_ui.api_client import APIError, auth_headers
from cue_ui.auth import CUE_API_URL, get_token, set_token_cookie
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
    documents: list[dict] = []
    web_ingest_enabled = False
    web_consent = False
    try:
        stats = await api_client.get_session_stats(token)
        documents = stats.get("documents", [])
        web_ingest_enabled = bool(stats.get("web_ingest_enabled", False))
        web_consent = bool(stats.get("web_consent", False))
    except APIError:
        pass
    return templates.TemplateResponse(
        request,
        "documents.html",
        {
            "session_id": session_id,
            "warning": warning,
            "documents": documents,
            "web_ingest_enabled": web_ingest_enabled,
            "web_consent": web_consent,
        },
    )


@router.get("/session/{session_id}/stats")
async def session_stats_proxy(request: Request, session_id: str):
    """Minimal proxy for /session/stats so review.js can refresh the docs list
    and `last_upload_at` after a mid-review upload without reloading the page.
    """
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        stats = await api_client.get_session_stats(token)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(
        {
            "documents": stats.get("documents", []),
            "last_upload_at": stats.get("last_upload_at"),
            "web_ingest_enabled": bool(stats.get("web_ingest_enabled", False)),
            "web_consent": bool(stats.get("web_consent", False)),
        }
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


@router.post("/session/{session_id}/web/preview")
async def web_preview_proxy(request: Request, session_id: str):  # noqa: ARG001 - session_id matches review.js path
    """Forward a URL preview request to the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid or missing JSON body"}, status_code=400)
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse({"detail": "Empty url"}, status_code=400)
    try:
        data = await api_client.web_preview(token, url)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(data)


@router.post("/session/{session_id}/web/ingest")
async def web_ingest_proxy(request: Request, session_id: str):  # noqa: ARG001
    """Forward a URL ingest request to the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid or missing JSON body"}, status_code=400)
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse({"detail": "Empty url"}, status_code=400)
    try:
        data = await api_client.web_ingest(token, url)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(data)


@router.put("/session/{session_id}/web-consent")
async def web_consent_proxy(request: Request, session_id: str):  # noqa: ARG001
    """Toggle the session-level web-consent flag via the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid or missing JSON body"}, status_code=400)
    enabled = bool(body.get("enabled"))
    try:
        data = await api_client.set_web_consent(token, enabled)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(data)


@router.delete("/session/{session_id}/documents/{name}")
async def remove_document_proxy(request: Request, session_id: str, name: str):  # noqa: ARG001
    """Forward a per-source remove request to the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        data = await api_client.remove_document(token, name)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse(data)


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
    last_upload_at: str | None = None
    web_ingest_enabled = False
    web_consent = False
    try:
        stats = await api_client.get_session_stats(token)
        documents = stats.get("documents", [])
        last_upload_at = stats.get("last_upload_at")
        web_ingest_enabled = bool(stats.get("web_ingest_enabled", False))
        web_consent = bool(stats.get("web_consent", False))
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
            "survey_format": survey_format,
            "can_submit": can_submit,
            "form_values": {},
            "documents": documents,
            "last_upload_at": last_upload_at,
            "review_state": review_state,
            "cached_suggestions": cached_suggestions,
            "web_ingest_enabled": web_ingest_enabled,
            "web_consent": web_consent,
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
            if q_type == "descriptive":
                continue
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


_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


async def _stream_suggestions_proxy(token: str, session_id: str, items: list[dict]):
    """Pump SSE 'suggestion' events from POST /suggest/stream upstream, rendering each
    payload through the suggestion_block partial. Shared by suggest-stream and
    regenerate-stream — they differ only in how `items` is built.
    """
    body = {"assessment_id": session_id, "items": items}
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
                        yield f"event: error\ndata: {line[len('data:') :].strip()}\n\n"
                        return
    except Exception as e:
        logger.error("SSE proxy error: %s", e)
        yield 'event: error\ndata: {"message": "Suggestion stream failed."}\n\n'


@router.get("/session/{session_id}/suggest-stream")
async def suggest_stream(session_id: str, request: Request):
    """SSE proxy: streams suggestion HTML blocks for items that have no cached suggestion yet."""
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
            all_cached_generator(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    return StreamingResponse(
        _stream_suggestions_proxy(token, session_id, items),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/session/{session_id}/regenerate-stream")
async def regenerate_stream(session_id: str, request: Request, ids: str | None = None):
    """SSE proxy that re-runs suggestion generation regardless of cache state.

    Mirrors `/suggest-stream` but skips the cached-IDs filter; the upstream
    `_cache_suggestion` is an upsert so re-running an item overwrites its entry.
    """
    token = get_token(request)
    if not token:
        return HTMLResponse("Unauthorized", status_code=401)

    try:
        survey = await api_client.get_survey(token, session_id)
    except APIError as exc:
        return HTMLResponse(f"Error: {exc.detail}", status_code=exc.status_code)

    items = _survey_to_batch_items(survey)
    if ids:
        wanted = {i.strip() for i in ids.split(",") if i.strip()}
        items = [item for item in items if item["id"] in wanted]

    if not items:

        async def empty_generator():
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            empty_generator(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    return StreamingResponse(
        _stream_suggestions_proxy(token, session_id, items),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
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


@router.get("/session/{session_id}/audit-report", response_class=HTMLResponse)
async def audit_report_page(request: Request, session_id: str):
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
        markdown_text = await api_client.fetch_audit_report_markdown(token=token)
    except APIError as exc:
        return _render_error(request, f"Could not load audit report: {exc.detail}", exc.status_code)
    return templates.TemplateResponse(
        request,
        "audit_report.html",
        {"session_id": session_id, "report_markdown": markdown_text},
    )


_CRED_FIELDS = {"api_url", "username", "password", "api_token", "datacenter_id"}
_RETRY_ECHO_FIELDS = {"api_url", "username", "datacenter_id"}


@router.post("/session/{session_id}/submit")
async def submit_responses(request: Request, session_id: str):
    """Collect form data, call submit API, redirect to submitted.html or show error.

    Form fields are partitioned: question answers (``q_*``) go to the API as
    ``responses``; named credential fields (``api_url`` etc.) go as
    ``credentials``. Password and api_token are never echoed back on retry —
    the browser's autofill handles re-population.
    """
    token = get_token(request)
    if not token:
        return RedirectResponse(url="/auth/login", status_code=302)

    form = await request.form()
    responses: dict[str, str | list[str]] = {}
    credentials: dict[str, str] = {}
    for k, v in form.multi_items():
        if k.startswith("_"):
            continue
        if k in _CRED_FIELDS:
            value = str(v).strip()
            if value:
                credentials[k] = value
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
        await api_client.submit_responses(
            token=token,
            session_id=session_id,
            responses=responses,
            credentials=credentials or None,
        )
    except APIError as exc:
        try:
            survey = await api_client.get_survey(token=token, survey_id=session_id)
        except APIError:
            survey = {}
        form_values: dict[str, str | list[str]] = dict(responses)
        for k in _RETRY_ECHO_FIELDS:
            if k in credentials:
                form_values[k] = credentials[k]
        return templates.TemplateResponse(
            request,
            "survey.html",
            {
                "session_id": session_id,
                "survey": survey,
                "survey_format": survey.get("metadata", {}).get("format", ""),
                "can_submit": True,
                "submit_error": exc.detail,
                "form_values": form_values,
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


@router.delete("/session/{session_id}")
async def delete_session_by_id(request: Request, session_id: str):
    """Delete a specific user-owned session.

    Rotates the auth cookie to a fresh session-less JWT iff the upstream
    response carries a `token` — i.e. the deleted session was the cookie's
    currently-bound one. Without this rotation, the stale `session_id` claim
    would resurrect the deleted session via the auth middleware on the next
    request.
    """
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        data = await api_client.delete_session_by_id(token, session_id)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    response = JSONResponse({"status": "deleted"}, status_code=200)
    new_token = data.get("token")
    if new_token:
        set_token_cookie(response, new_token)
    return response


# ---------------------------------------------------------------------------
# Review state proxy (UI → Cue API)
# ---------------------------------------------------------------------------


@router.put("/review-state/{question_id}")
async def save_review_state(request: Request, question_id: str):
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


@router.get("/review-state")
async def get_review_state(request: Request):
    """Proxy review state load from the Cue API."""
    token = get_token(request)
    if not token:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    try:
        states = await api_client.get_review_state(token)
    except APIError as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return {"states": states}
