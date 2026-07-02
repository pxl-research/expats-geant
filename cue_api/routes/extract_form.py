"""Cue API: LLM-assisted form-field extraction for the browser extension."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from cue_api.models import BatchSuggestItem, ExtractFormRequest
from m_shared.llm.client import LLMClient
from m_shared.rate_limit import limiter
from m_shared.utils.llm_parsing import extract_json_object

logger = logging.getLogger(__name__)

router = APIRouter()


_EXTRACTION_SYSTEM_PROMPT = """You analyze the plain-text content of a web page and identify any form fields it contains.

Return STRICT JSON of the form:
{"items": [{"id": "q1", "type": "open_ended", "prompt": "...", "choices": [{"id": "c1", "label": "..."}]}]}

Rules:
- "type" MUST be one of: open_ended, single_choice, multiple_choice, slider.
- "choices" is REQUIRED and non-empty for single_choice and multiple_choice.
- "choices" MUST be omitted (or empty) for open_ended and slider.
- "id" values are short synthetic identifiers (q1, q2, ...). They do not need to match the page.
- "prompt" is the question or field-label text as it appears to the user.
- If the text contains no form fields, return {"items": []}.
- Do not include explanatory prose; the response MUST be parseable JSON only."""


def _build_extraction_messages(url: str, page_text: str) -> list[dict]:
    return [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Source URL: {url}\n\nPage text:\n{page_text}",
        },
    ]


def _parse_extraction_response(raw: str) -> list[BatchSuggestItem]:
    """Parse an LLM extraction response into validated BatchSuggestItem entries.

    Drops individual items that fail Pydantic validation; returns an empty list
    only when the LLM legitimately reported no fields. Raises ValueError when
    the response is structurally unparseable.
    """
    parsed = json.loads(extract_json_object(raw.strip()))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        raise ValueError("LLM response did not contain an 'items' list")

    items: list[BatchSuggestItem] = []
    for raw_item in parsed["items"]:
        if not isinstance(raw_item, dict):
            continue
        try:
            items.append(BatchSuggestItem(**raw_item))
        except ValidationError as exc:
            logger.warning("Dropping malformed extracted item: %s", exc.errors()[:1])
    return items


def _extract_form_items(llm_client: LLMClient, url: str, page_text: str) -> list[BatchSuggestItem]:
    """Call the LLM to extract form items from page text.

    Raises:
        RuntimeError: on LLM call failure, empty response, or unparseable JSON.
    """
    messages = _build_extraction_messages(url, page_text)
    try:
        raw = llm_client.create_completion(messages=messages, temperature=0.0)
    except Exception as exc:
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    if not raw or not raw.strip():
        raise RuntimeError("LLM returned empty response")

    try:
        return _parse_extraction_response(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Failed to parse LLM response: {exc}") from exc


@router.post("/extract-form", response_model=list[BatchSuggestItem])
@limiter.limit("10/minute")
async def extract_form(request: Request, body: ExtractFormRequest) -> list[BatchSuggestItem]:
    """Extract form-field BatchSuggestItems from a page's plain text.

    Reserved for the browser extension's third-tier LLM fallback. Deterministic
    extractors (known-platform, semantic HTML) SHOULD be tried first client-side.
    """
    llm_client: LLMClient | None = request.app.state.llm_client
    if llm_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM client is not configured for this deployment",
        )

    session = request.state.session
    claims = request.state.claims
    audit_logger = request.app.state.audit_logger

    try:
        items = _extract_form_items(llm_client, body.url, body.page_text)
    except RuntimeError as exc:
        logger.warning("Form extraction failed for %s: %s", body.url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Form extraction failed",
        ) from exc

    if audit_logger:
        audit_logger.log_extract_form(
            session_id=session.session_id,
            url=body.url,
            item_count=len(items),
            model=llm_client.model_name,
            user_id=claims.get("user_id"),
        )

    return items
