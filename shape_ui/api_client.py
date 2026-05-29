"""HTTP client wrapper for Shape API calls."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SHAPE_API_URL = os.getenv("SHAPE_API_URL", "http://localhost:8802")


class APIError(Exception):
    """Raised when the Shape API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _format_validation_errors(items: list) -> str:
    """Flatten FastAPI's structured 422 detail list into a readable single line.

    FastAPI emits validation errors as `[{type, loc, msg, input}, ...]`. We join
    them as `loc.path: msg; loc.path: msg`, stripping the noisy leading `body.`
    that FastAPI adds to request-body errors.
    """
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        loc = list(item.get("loc") or [])
        if loc and loc[0] == "body":
            loc = loc[1:]
        loc_str = ".".join(str(p) for p in loc) or "(root)"
        msg = item.get("msg", "validation error")
        parts.append(f"{loc_str}: {msg}")
    return "; ".join(parts) if parts else "validation error"


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise APIError for 4xx/5xx responses.

    Handles three `detail` shapes the Shape API may return:
    - string (legacy 4xx with a hand-rolled detail) → used verbatim
    - list (FastAPI's typed-Pydantic 422 format) → flattened to a readable string
    - anything else / missing → falls back to repr or `resp.text`
    """
    if resp.is_error:
        try:
            detail: Any = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        if isinstance(detail, list):
            detail = _format_validation_errors(detail)
        elif not isinstance(detail, str):
            detail = repr(detail)
        raise APIError(status_code=resp.status_code, detail=detail)


async def create_session(token: str) -> dict[str, Any]:
    """Create a new chat session.

    POST /chat/sessions → ChatSessionResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/sessions",
            headers=_auth_headers(token),
            json={},
        )
    _raise_for_status(resp)
    return resp.json()


async def select_session(token: str, session_id: str) -> dict[str, Any]:
    """Select/resume a chat session. Returns a new JWT scoped to it.

    POST /chat/sessions/{session_id}/select → ChatSessionResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/sessions/{session_id}/select",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def list_sessions(token: str) -> list[dict[str, Any]]:
    """List all chat sessions for the authenticated user.

    GET /chat/sessions → ChatSessionListResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHAPE_API_URL}/chat/sessions",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    data = resp.json()
    return data.get("sessions", [])


async def get_session(token: str, session_id: str) -> dict[str, Any]:
    """Get metadata for a specific chat session.

    GET /chat/{session_id} → ChatSessionResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHAPE_API_URL}/chat/{session_id}",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def send_message(token: str, session_id: str, message: str) -> dict[str, Any]:
    """Send a message to the chat session and get a response.

    POST /chat/{session_id} → ChatTurnResponse
    """
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/{session_id}",
            headers=_auth_headers(token),
            json={"message": message},
        )
    _raise_for_status(resp)
    return resp.json()


async def get_survey(token: str, session_id: str) -> dict[str, Any] | None:
    """Get the current draft survey for a chat session.

    GET /chat/{session_id}/survey → ChatSurveyResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHAPE_API_URL}/chat/{session_id}/survey",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    data = resp.json()
    return data.get("survey")


async def get_style(token: str, session_id: str) -> dict[str, Any]:
    """Get the style profile for a chat session.

    GET /chat/{session_id}/style → StyleProfileResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHAPE_API_URL}/chat/{session_id}/style",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    data = resp.json()
    return data.get("style_profile", {})


async def update_style(
    token: str, session_id: str, language: str | None, free_text: str | None
) -> dict[str, Any]:
    """Update language and/or free_text in the style profile.

    PUT /chat/{session_id}/style → StyleProfileResponse
    """
    payload: dict[str, Any] = {}
    if language is not None:
        payload["language"] = language
    if free_text is not None:
        payload["free_text"] = free_text
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{SHAPE_API_URL}/chat/{session_id}/style",
            headers=_auth_headers(token),
            json=payload,
        )
    _raise_for_status(resp)
    data = resp.json()
    return data.get("style_profile", {})


async def upload_style_doc(
    token: str, session_id: str, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    """Upload a style guide document to update the session style profile.

    POST /chat/{session_id}/style/upload → DocumentUploadResponse
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/{session_id}/style/upload",
            headers=_auth_headers(token),
            files={"file": (filename, file_bytes)},
        )
    _raise_for_status(resp)
    return resp.json()


async def upload_content_doc(
    token: str, session_id: str, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    """Upload a content document to provide context for chat turns.

    POST /chat/{session_id}/upload → DocumentUploadResponse
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/{session_id}/upload",
            headers=_auth_headers(token),
            files={"file": (filename, file_bytes)},
        )
    _raise_for_status(resp)
    return resp.json()


async def export_survey(token: str, session_id: str, fmt: str) -> dict[str, Any]:
    """Export survey to a platform-specific format via the survey payload.

    POST /export → ExportResponse
    """
    survey = await get_survey(token, session_id)
    if survey is None:
        raise APIError(status_code=404, detail="No draft survey found for this session")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/export",
            headers=_auth_headers(token),
            json={"format": fmt, "survey": survey},
        )
    _raise_for_status(resp)
    return resp.json()


async def create_survey_on_platform(
    token: str,
    session_id: str,
    fmt: str,
    api_url: str | None = None,
    platform_token: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Create survey on the target platform or fall back to file export.

    POST /create → CreateResponse
    """
    survey = await get_survey(token, session_id)
    if survey is None:
        raise APIError(status_code=404, detail="No draft survey found for this session")
    payload: dict[str, Any] = {"format": fmt, "survey": survey}
    if api_url:
        payload["api_url"] = api_url
    if platform_token:
        payload["token"] = platform_token
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/create",
            headers=_auth_headers(token),
            json=payload,
        )
    _raise_for_status(resp)
    return resp.json()


async def get_messages(token: str, session_id: str) -> list[dict[str, Any]]:
    """Get conversation history for a chat session.

    GET /chat/{session_id}/messages → {"messages": [...]}
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHAPE_API_URL}/chat/{session_id}/messages",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json().get("messages", [])


async def reset_session(token: str, session_id: str) -> dict[str, Any]:
    """Clear draft survey and tag vocabulary, leaving conversation history.

    POST /chat/{session_id}/reset
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SHAPE_API_URL}/chat/{session_id}/reset",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def delete_session(token: str, session_id: str) -> dict[str, Any]:
    """Delete a chat session and all its data.

    DELETE /chat/{session_id}
    """
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{SHAPE_API_URL}/chat/{session_id}",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def get_conversation(token: str, session_id: str) -> list[dict[str, Any]]:
    """Retrieve conversation history by loading the session.

    Uses GET /chat/{session_id} — conversation history is not directly exposed
    by the API, so we return an empty list here (UI builds it from sends).
    """
    # The shape_api API doesn't have a dedicated conversation history endpoint;
    # the chat page loads history from session context.
    # Return empty list; actual messages are accumulated client-side via HTMX.
    return []
