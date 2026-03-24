"""HTTP client wrapper for M-Chat API calls."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MCHAT_API_URL = os.getenv("MCHAT_API_URL", "http://localhost:8003")


class APIError(Exception):
    """Raised when the M-Chat API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise APIError for 4xx/5xx responses."""
    if resp.is_error:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APIError(status_code=resp.status_code, detail=detail)


async def create_session(token: str) -> dict[str, Any]:
    """Create a new chat session.

    POST /chat/sessions → ChatSessionResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MCHAT_API_URL}/chat/sessions",
            headers=_auth_headers(token),
            json={},
        )
    _raise_for_status(resp)
    return resp.json()


async def list_sessions(token: str) -> list[dict[str, Any]]:
    """List all chat sessions for the authenticated user.

    GET /chat/sessions → ChatSessionListResponse
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{MCHAT_API_URL}/chat/sessions",
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
            f"{MCHAT_API_URL}/chat/{session_id}",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def send_message(token: str, session_id: str, message: str) -> dict[str, Any]:
    """Send a message to the chat session and get a response.

    POST /chat/{session_id} → ChatTurnResponse
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{MCHAT_API_URL}/chat/{session_id}",
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
            f"{MCHAT_API_URL}/chat/{session_id}/survey",
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
            f"{MCHAT_API_URL}/chat/{session_id}/style",
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
            f"{MCHAT_API_URL}/chat/{session_id}/style",
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
            f"{MCHAT_API_URL}/chat/{session_id}/style/upload",
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
            f"{MCHAT_API_URL}/chat/{session_id}/upload",
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
            f"{MCHAT_API_URL}/export",
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
            f"{MCHAT_API_URL}/create",
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
            f"{MCHAT_API_URL}/chat/{session_id}/messages",
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
            f"{MCHAT_API_URL}/chat/{session_id}/reset",
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
            f"{MCHAT_API_URL}/chat/{session_id}",
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
