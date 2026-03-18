"""HTTP client wrapper for M-Autofill API calls."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

AUTOFILL_API_URL = os.getenv("AUTOFILL_API_URL", "http://localhost:8001")


class APIError(Exception):
    """Raised when the M-Autofill API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def get_survey(token: str, survey_id: str) -> dict[str, Any]:
    """Fetch survey by ID from M-Autofill API.

    GET /surveys/{survey_id} → Survey dict
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{AUTOFILL_API_URL}/surveys/{survey_id}",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    return resp.json()


async def get_capabilities(token: str, format: str) -> set[str]:
    """Fetch adapter capabilities for a given survey format.

    GET /adapters/{format}/capabilities → set[str]
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{AUTOFILL_API_URL}/adapters/{format}/capabilities",
            headers=_auth_headers(token),
        )
    _raise_for_status(resp)
    data = resp.json()
    # API may return list or set (JSON array)
    if isinstance(data, list):
        return set(data)
    return set(data)


async def batch_suggest(
    token: str, session_id: str, survey_id: str, items: list[dict]
) -> list[dict]:
    """Fetch AI suggestions for all questions in a survey session.

    POST /suggest/batch → list of ItemSuggestion dicts
    """
    payload = {"assessment_id": survey_id, "items": items}
    logger.debug("batch_suggest payload: %s", payload)
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{AUTOFILL_API_URL}/suggest/batch",
            headers=_auth_headers(token),
            json=payload,
        )
    if resp.is_error:
        logger.error("batch_suggest %s: %s", resp.status_code, resp.text)
    _raise_for_status(resp)
    data = resp.json()
    return data.get("responses", [])


async def submit_responses(token: str, session_id: str, responses: dict[str, Any]) -> None:
    """Submit survey responses via M-Autofill adapter.

    POST /sessions/{session_id}/submit
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AUTOFILL_API_URL}/sessions/{session_id}/submit",
            headers=_auth_headers(token),
            json=responses,
        )
    _raise_for_status(resp)


async def import_survey_file(
    token: str, file_bytes: bytes, filename: str, format: str
) -> tuple[str, str | None]:
    """Upload and import a survey file, returning (survey_id, warning).

    POST /surveys/import → {"survey_id": "...", "warning": "..." | null}
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{AUTOFILL_API_URL}/surveys/import",
            headers=_auth_headers(token),
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
            f"{AUTOFILL_API_URL}/surveys/import-from-api",
            headers=_auth_headers(token),
            json=payload,
        )
    _raise_for_status(resp)
    data = resp.json()
    return data["survey_id"], data.get("warning")


async def ingest_document(token: str, session_id: str, file_bytes: bytes, filename: str) -> None:
    """Forward a document to the M-Autofill ingestion API.

    POST /upload — UI holds no document content.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{AUTOFILL_API_URL}/upload",
            headers=_auth_headers(token),
            files={"file": (filename, file_bytes)},
        )
    _raise_for_status(resp)


async def ingest_text_snippet(token: str, session_id: str, text: str, label: str | None) -> None:
    """Forward a text snippet to the M-Autofill ingestion API.

    POST /upload-text — UI holds no text content after forwarding.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{AUTOFILL_API_URL}/upload-text",
            headers=_auth_headers(token),
            json={"text": text, "label": label},
        )
    _raise_for_status(resp)


async def fetch_answer_report(token: str, session_id: str) -> list[dict] | None:
    """Fetch the session answer report.

    GET /answer-report/download → parsed list, or None if no suggestions yet.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{AUTOFILL_API_URL}/answer-report/download",
            headers=_auth_headers(token),
        )
    if resp.status_code == 404:
        return None
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
