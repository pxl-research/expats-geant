"""Cue API: survey import, retrieval, and response submission routes."""

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from cue_api.models import LiveApiImportRequest, SubmitCredentials, SubmitResponsesRequest
from m_shared.adapters.registry import get_adapter
from m_shared.models.response import Response as SurveyResponse
from m_shared.utils.url_validation import validate_api_url, validate_datacenter_id

logger = logging.getLogger(__name__)

router = APIRouter()


def _platform_error_detail(exc: RuntimeError) -> str:
    """Return an actionable 502 detail from a platform RuntimeError.

    Classifies the error into one of three buckets without echoing credentials.
    """
    msg = str(exc).lower()
    if "authentication failed" in msg:
        return "Authentication failed. Check your credentials and try again."
    if any(k in msg for k in ("connection", "timeout", "refused", "unreachable", "max retries")):
        return "Could not reach the platform. Check the API URL and network connectivity."
    return f"The platform returned an error: {exc}"


def _translate_to_platform_code(answer_value: Any, option_values: dict[str, str]) -> Any:
    """Map internal option ids (e.g. ``opt_A1``) to platform answer codes
    (e.g. ``A1``) before the adapter builds its platform-specific payload.

    The HTML form submits ``option.id`` (because that's the natural html value
    of a checkbox / radio), but LimeSurvey's SGQA sub-question suffix and
    Qualtrics' choice code use ``option.value`` — the platform's own code,
    stashed on the AnswerOption at import time. Without this translation the
    upstream call silently drops the answer (the SGQA key never matches a
    column, the QID choice code doesn't resolve).

    Unknown values pass through unchanged so free-text and slider answers
    are not mangled.
    """
    if not option_values:
        return answer_value
    if isinstance(answer_value, list):
        return [option_values.get(item, item) for item in answer_value]
    if isinstance(answer_value, str):
        return option_values.get(answer_value, answer_value)
    return answer_value


def _build_responses_from_body(
    body: dict, question_meta: dict, session_id: str
) -> list[SurveyResponse]:
    """Convert a form-field body dict to a list of SurveyResponse objects."""
    responses: list[SurveyResponse] = []
    for field_key, answer_value in body.items():
        if field_key.startswith("_"):
            continue
        question_id = field_key[2:] if field_key.startswith("q_") else field_key
        q_meta = question_meta.get(question_id, {})
        translated = _translate_to_platform_code(answer_value, q_meta.get("_option_values", {}))
        responses.append(
            SurveyResponse(
                id=str(uuid.uuid4()),
                question_id=question_id,
                answer_value=translated,
                session_id=session_id,
                metadata={"ls_qid": q_meta["ls_qid"]} if "ls_qid" in q_meta else {},
            )
        )
    return responses


_CREDENTIAL_ENV: dict[str, tuple[tuple[str, str], ...]] = {
    "lss": (
        ("api_url", "LIMESURVEY_API_URL"),
        ("username", "LIMESURVEY_USERNAME"),
        ("password", "LIMESURVEY_PASSWORD"),
    ),
    "limesurvey": (
        ("api_url", "LIMESURVEY_API_URL"),
        ("username", "LIMESURVEY_USERNAME"),
        ("password", "LIMESURVEY_PASSWORD"),
    ),
    "qsf": (
        ("api_token", "QUALTRICS_API_TOKEN"),
        ("datacenter_id", "QUALTRICS_DATACENTER_ID"),
    ),
}


def _resolve_submit_credentials(
    fmt: str, body_creds: SubmitCredentials | None
) -> dict[str, str | None]:
    """Resolve adapter credentials with per-key precedence: body → env → None.

    Never logs or persists the returned values; the caller passes them
    straight to the adapter constructor and discards them on return.
    """
    mapping = _CREDENTIAL_ENV.get(fmt)
    if mapping is None:
        return {}
    return {
        key: (getattr(body_creds, key, None) if body_creds else None) or os.getenv(env_var)
        for key, env_var in mapping
    }


@router.post("/surveys/import", tags=["Surveys"])
async def import_survey(
    request: Request,
    file: UploadFile = File(...),
    format: str = Form(...),
):
    """Parse a survey file and store it for the current session."""
    session = request.state.session
    manager = request.state.session_manager

    try:
        adapter = get_adapter(format)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported format '{format}'. Supported: qsf, lss, qti, sm.",
        )

    max_survey_bytes = 10 * 1024 * 1024  # 10 MB — generous for any survey file
    content = await file.read(max_survey_bytes + 1)
    if len(content) > max_survey_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Survey file too large (max 10 MB)",
        )
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey file must be UTF-8 encoded text (XML or JSON).",
        )

    try:
        survey = adapter.import_survey(content_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse survey: {exc}",
        )

    survey.metadata["format"] = format

    session_path = manager._get_session_path(session.session_id)
    session_path.mkdir(parents=True, exist_ok=True)
    (session_path / "survey.json").write_text(survey.model_dump_json())

    total_questions = sum(len(s.questions) for s in survey.sections)
    warning = (
        "No answerable questions were extracted. "
        "The file may contain only display elements or unsupported question types."
        if total_questions == 0
        else None
    )
    return {"survey_id": session.session_id, "warning": warning}


@router.post("/surveys/import-from-api", tags=["Surveys"])
async def import_survey_from_api(request: Request, body: LiveApiImportRequest):
    """Fetch a survey directly from LimeSurvey or Qualtrics and store for the session."""
    session = request.state.session
    manager = request.state.session_manager

    if body.format not in ("lss", "qsf"):
        raise HTTPException(
            status_code=422,
            detail=f"Live API import only supported for 'lss' and 'qsf'. Got: '{body.format}'.",
        )

    if body.format == "lss":
        if body.api_url:
            # validate_api_url does a blocking DNS lookup; keep it off the event loop.
            await asyncio.to_thread(validate_api_url, body.api_url)
        adapter_kwargs = {
            "api_url": body.api_url,
            "username": body.username,
            "password": body.password,
        }
    else:  # qsf
        if body.datacenter_id:
            validate_datacenter_id(body.datacenter_id)
        adapter_kwargs = {
            "api_token": body.api_token,
            "datacenter_id": body.datacenter_id,
        }

    try:
        adapter = get_adapter(body.format, **adapter_kwargs)
    except KeyError:
        raise HTTPException(status_code=422, detail=f"No adapter for format '{body.format}'.")

    try:
        survey = adapter.fetch_survey(body.survey_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Platform API call failed for format '%s': %s", body.format, exc)
        raise HTTPException(status_code=502, detail=_platform_error_detail(exc))

    survey.metadata["format"] = body.format

    session_path = manager._get_session_path(session.session_id)
    session_path.mkdir(parents=True, exist_ok=True)
    (session_path / "survey.json").write_text(survey.model_dump_json())

    total_questions = sum(len(s.questions) for s in survey.sections)
    warning = (
        "No answerable questions were extracted. "
        "The file may contain only display elements or unsupported question types."
        if total_questions == 0
        else None
    )
    logger.info(
        "Live API import completed for format '%s', session %s", body.format, session.session_id
    )
    return {"survey_id": session.session_id, "warning": warning}


@router.get("/surveys/{survey_id}", tags=["Surveys"])
async def get_survey(request: Request, survey_id: str):
    """Retrieve a previously imported survey by ID."""
    session = request.state.session
    if survey_id != session.session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: survey belongs to a different session.",
        )
    manager = request.state.session_manager
    survey_path = manager._get_session_path(survey_id) / "survey.json"

    if not survey_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey '{survey_id}' not found or session expired.",
        )

    return json.loads(survey_path.read_text())


@router.get("/adapters/{format}/capabilities", tags=["Adapters"])
async def get_adapter_capabilities(format: str):
    """Return the capabilities supported by the adapter for a given format."""
    try:
        adapter = get_adapter(format)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No adapter for format '{format}'. Supported: qsf, lss, qti, sm.",
        )
    return sorted(adapter.capabilities())


@router.post("/sessions/{session_id}/submit", tags=["Surveys"])
async def submit_session_responses(request: Request, session_id: str, body: SubmitResponsesRequest):
    """Submit survey responses to the originating platform.

    Credentials are resolved with per-key precedence: request body → env vars
    (`LIMESURVEY_*` / `QUALTRICS_*`) → None. Never logged, never persisted.
    """
    session = request.state.session
    if session_id != session.session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: session belongs to a different user.",
        )

    manager = request.state.session_manager
    survey_path = manager._get_session_path(session_id) / "survey.json"

    if not survey_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey '{session_id}' not found or session expired.",
        )

    survey_data = json.loads(survey_path.read_text())
    survey_format = survey_data.get("metadata", {}).get("format", "")

    if not survey_format:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Survey has no format metadata — cannot determine submission adapter.",
        )

    # Resolved credentials must never appear in logs.
    adapter_kwargs = _resolve_submit_credentials(survey_format, body.credentials)
    missing = [k for k, v in adapter_kwargs.items() if not v]
    if adapter_kwargs and missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Missing required credentials for '{survey_format}': "
                f"{', '.join(missing)}. Supply them in the request body or set "
                "the corresponding environment variables."
            ),
        )

    if body.credentials and body.credentials.api_url:
        # validate_api_url is blocking (DNS); offload like /surveys/import-from-api does.
        await asyncio.to_thread(validate_api_url, body.credentials.api_url)

    try:
        adapter = get_adapter(survey_format, **adapter_kwargs)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No adapter for format '{survey_format}'.",
        )

    if "submit" not in adapter.capabilities():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Adapter for '{survey_format}' does not support response submission.",
        )

    question_meta: dict[str, dict] = {}
    for section in survey_data.get("sections", []):
        for q in section.get("questions", []):
            meta = dict(q.get("metadata", {}))
            # Stash the option_id → platform_code map so _build_responses_from_body
            # can translate the HTML form's option ids back to the codes the
            # platform's submit API expects (SGQA suffix for LS, choice code for QSF).
            meta["_option_values"] = {
                opt["id"]: opt["value"]
                for opt in q.get("answer_options", [])
                if "id" in opt and opt.get("value") is not None
            }
            question_meta[q["id"]] = meta

    responses = _build_responses_from_body(body.responses, question_meta, session_id)

    platform_survey_id = survey_data.get("id", session_id)
    try:
        adapter.submit_responses(survey_id=platform_survey_id, responses=responses)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Adapter for '{survey_format}' does not support response submission.",
        )
    except (ValueError, RuntimeError) as exc:
        logger.error("Submission to platform failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Submission to platform failed",
        )

    return {"status": "submitted", "session_id": session_id}
