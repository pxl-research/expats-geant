"""Shape API: survey import, export, and create routes."""

import asyncio

from fastapi import APIRouter, HTTPException, status

from m_shared.adapters.base import SurveyAdapter
from m_shared.adapters.registry import get_adapter
from m_shared.utils.url_validation import validate_api_url, validate_datacenter_id
from shape_api.models import (
    CreateRequest,
    CreateResponse,
    ExportRequest,
    ExportResponse,
    ImportRequest,
    ImportResponse,
)

router = APIRouter()


def _get_adapter(
    fmt: str,
    api_url: str | None,
    token: str | None,
    username: str | None,
    password: str | None,
) -> SurveyAdapter:
    """Instantiate adapter for the given format with optional credentials.

    Raises:
        HTTPException: 422 if format is not recognised, 400 if api_url is unsafe.
    """
    try:
        if fmt in ("limesurvey", "lss"):
            if api_url:
                validate_api_url(api_url)
            return get_adapter(fmt, api_url=api_url, username=username, password=password)
        elif fmt in ("qualtrics", "qsf"):
            if api_url:
                validate_datacenter_id(api_url)
            return get_adapter(fmt, api_token=token, datacenter_id=api_url)
        else:
            return get_adapter(fmt)
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unknown format '{fmt}'. "
                "Supported: limesurvey, lss, qualtrics, qsf, qti, surveymonkey, sm."
            ),
        )


@router.post("/import", response_model=ImportResponse)
async def import_survey(body: ImportRequest):
    """Parse a platform survey file and return the internal Survey JSON."""
    adapter = _get_adapter(body.format, None, None, None, None)
    try:
        survey = adapter.import_survey(body.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse survey: {exc}",
        )
    return ImportResponse(survey=survey)


@router.post("/export", response_model=ExportResponse)
async def export_survey(body: ExportRequest):
    """Serialise an internal Survey to a platform-specific format."""
    adapter = _get_adapter(body.format, None, None, None, None)
    try:
        content = adapter.export_survey(body.survey)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not serialise survey: {exc}",
        )
    return ExportResponse(format=body.format, content=content)


@router.post("/create", response_model=CreateResponse)
async def create_survey_endpoint(body: CreateRequest):
    """Create a survey on the target platform or fall back to file export.

    Adapter exceptions are translated to HTTPException with the actual message
    intact so the UI can display the underlying cause (e.g. an upstream auth
    failure) rather than FastAPI's generic ``500 Internal Server Error``.
    """
    # _get_adapter calls validate_api_url, which does a blocking DNS lookup.
    adapter = await asyncio.to_thread(
        _get_adapter, body.format, body.api_url, body.token, body.username, body.password
    )
    survey = body.survey

    credentials_present = any([body.api_url, body.token, body.username, body.password])

    if credentials_present and "create" in adapter.capabilities():
        try:
            # adapter.create_survey is blocking (requests) — offload like _get_adapter.
            content = await asyncio.to_thread(adapter.create_survey, survey)
            created_via = "api" if "api_create" in adapter.capabilities() else "file_export"
        except NotImplementedError:
            content = _safe_export(adapter, survey)
            created_via = "file_export"
        except ValueError as exc:
            # Missing/invalid credentials → 400 with the adapter's own message.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        except RuntimeError as exc:
            # Upstream platform failure (auth, RPC, network) — surface the
            # adapter's message verbatim so the user can act on it. 502 marks
            # this as an upstream-platform issue rather than a Shape API bug.
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    else:
        content = _safe_export(adapter, survey)
        created_via = "file_export"

    return CreateResponse(format=body.format, platform_id=content, created_via=created_via)


def _safe_export(adapter: SurveyAdapter, survey) -> str:
    """Run ``export_survey`` and translate parse/serialise errors to 400."""
    try:
        return adapter.export_survey(survey)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not serialise survey: {exc}",
        )
