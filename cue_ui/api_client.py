"""HTTP client wrapper for Cue API calls."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CUE_API_URL = os.getenv("CUE_API_URL", "http://localhost:8801")


class APIError(Exception):
    """Raised when the Cue API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def get_survey(token: str, survey_id: str) -> dict[str, Any]:
    """Fetch survey by ID from Cue API.

    GET /surveys/{survey_id} → Survey dict
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/surveys/{survey_id}",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def get_capabilities(token: str, format: str) -> set[str]:
    """Fetch adapter capabilities for a given survey format.

    GET /adapters/{format}/capabilities → set[str]
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/adapters/{format}/capabilities",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    data = resp.json()
    # API may return list or set (JSON array)
    if isinstance(data, list):
        return set(data)
    return set(data)


async def submit_responses(
    token: str,
    session_id: str,
    responses: dict[str, Any],
    credentials: dict[str, str] | None = None,
) -> None:
    """Submit survey responses via Cue adapter.

    POST /sessions/{session_id}/submit with body
    ``{"responses": {...}, "credentials": {...} | omitted}``.
    """
    body: dict[str, Any] = {"responses": responses}
    if credentials:
        body["credentials"] = credentials
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CUE_API_URL}/sessions/{session_id}/submit",
            headers=auth_headers(token),
            json=body,
        )
    _raise_for_status(resp)


async def get_session_stats(token: str) -> dict[str, Any]:
    """Fetch session statistics from Cue API.

    GET /session/stats → session stats dict
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/session/stats",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def delete_session(token: str) -> None:
    """Delete the current session and all associated data.

    DELETE /session
    """
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{CUE_API_URL}/session",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)


async def delete_session_by_id(token: str, session_id: str) -> dict[str, Any]:
    """Delete one of the authenticated user's sessions by id.

    DELETE /sessions/{session_id}

    Response may include `token` — a fresh session-less JWT when the deleted
    session was the caller's currently-bound one. The caller is responsible
    for replacing the cookie with this token to avoid the stale-JWT
    resurrection branch in the auth middleware.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{CUE_API_URL}/sessions/{session_id}",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def remove_document(token: str, name: str) -> dict[str, Any]:
    """Remove a single source from the current session.

    DELETE /session/documents/{name}
    """
    from urllib.parse import quote

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{CUE_API_URL}/session/documents/{quote(name, safe='')}",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def import_survey_file(
    token: str, file_bytes: bytes, filename: str, format: str
) -> tuple[str, str | None]:
    """Upload and import a survey file, returning (survey_id, warning).

    POST /surveys/import → {"survey_id": "...", "warning": "..." | null}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/surveys/import",
            headers=auth_headers(token),
            data={"format": format},
            files={"file": (filename, file_bytes)},
        )
    _raise_for_status(resp)
    data = resp.json()
    return data["survey_id"], data.get("warning")


async def import_survey_from_api(
    token: str,
    format: str,
    survey_id: str,
    api_url: str | None = None,
    api_token: str | None = None,
    datacenter_id: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> tuple[str, str | None]:
    """POST /surveys/import-from-api → (session_survey_id, warning)."""
    payload = {
        "format": format,
        "survey_id": survey_id,
        "api_url": api_url,
        "api_token": api_token,
        "datacenter_id": datacenter_id,
        "username": username,
        "password": password,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/surveys/import-from-api",
            headers=auth_headers(token),
            json=payload,
        )
    _raise_for_status(resp)
    data = resp.json()
    return data["survey_id"], data.get("warning")


async def ingest_document(token: str, session_id: str, file_bytes: bytes, filename: str) -> None:  # noqa: ARG001
    """Forward a document to the Cue ingestion API.

    POST /upload — UI holds no document content.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/upload",
            headers=auth_headers(token),
            files={"file": (filename, file_bytes)},
        )
    _raise_for_status(resp)


async def ingest_text_snippet(token: str, session_id: str, text: str, label: str | None) -> None:
    """Forward a text snippet to the Cue ingestion API.

    POST /upload-text — UI holds no text content after forwarding.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/upload-text",
            headers=auth_headers(token),
            json={"text": text, "label": label},
        )
    _raise_for_status(resp)


async def web_preview(token: str, url: str) -> dict[str, Any]:
    """POST /web/preview → preview payload."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/web/preview",
            headers=auth_headers(token),
            json={"url": url},
        )
    _raise_for_status(resp)
    return resp.json()


async def web_ingest(token: str, url: str) -> dict[str, Any]:
    """POST /web/ingest → {status, source, source_url}."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{CUE_API_URL}/web/ingest",
            headers=auth_headers(token),
            json={"url": url},
        )
    _raise_for_status(resp)
    return resp.json()


async def set_web_consent(token: str, enabled: bool) -> dict[str, Any]:
    """PUT /session/web-consent → {web_consent: <bool>}."""
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{CUE_API_URL}/session/web-consent",
            headers=auth_headers(token),
            json={"enabled": enabled},
        )
    _raise_for_status(resp)
    return resp.json()


async def fetch_answer_report(token: str) -> list[dict] | None:
    """Fetch the session answer report.

    GET /answer-report/download → parsed list, or None if no suggestions yet.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/answer-report/download",
            headers=auth_headers(token),
        )
    if resp.status_code == 404:
        return None
    _raise_for_status(resp)
    return resp.json()


async def fetch_audit_report_markdown(token: str) -> str | None:
    """Fetch the session audit report in Markdown format.

    GET /audit-report?format=markdown → Markdown string, or None on 404.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/audit-report?format=markdown",
            headers=auth_headers(token),
        )
    if resp.status_code == 404:
        return None
    _raise_for_status(resp)
    return resp.text


async def save_review_state(token: str, question_id: str, state: dict) -> None:
    """Save review state for a single question.

    PUT /review-state/{question_id}
    """
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{CUE_API_URL}/review-state/{question_id}",
            headers=auth_headers(token),
            json=state,
        )
    _raise_for_status(resp)


async def get_review_state(token: str) -> dict:
    """Fetch full review state map for the session.

    GET /review-state → states dict, or {} if empty.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/review-state",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json().get("states", {})


async def get_cached_suggestions(token: str) -> dict:
    """Fetch cached suggestion objects for the session.

    GET /cached-suggestions → dict mapping question_id to ItemSuggestion, or {}.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CUE_API_URL}/cached-suggestions",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json().get("suggestions", {})


async def list_sessions(token: str) -> list[dict]:
    """Fetch all active sessions for the authenticated user."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CUE_API_URL}/sessions", headers=auth_headers(token))
    _raise_for_status(resp)
    return resp.json().get("sessions", [])


async def create_new_session(token: str) -> dict:
    """Create a new session. Returns {token, session_id}."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{CUE_API_URL}/sessions/new", headers=auth_headers(token))
    _raise_for_status(resp)
    return resp.json()


async def select_session(token: str, session_id: str) -> dict:
    """Select/resume a session. Returns {token, session_id}."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CUE_API_URL}/sessions/{session_id}/select",
            headers=auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise APIError for 4xx/5xx responses."""
    if resp.is_error:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(status_code=resp.status_code, detail=detail)
