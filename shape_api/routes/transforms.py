"""Shape API: survey import, export, and create routes."""

from fastapi import APIRouter, HTTPException, status

from m_shared.adapters.base import SurveyAdapter
from m_shared.adapters.registry import get_adapter
from m_shared.models.survey import Survey
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
    return ImportResponse(survey=survey.model_dump())


@router.post("/export", response_model=ExportResponse)
async def export_survey(body: ExportRequest):
    """Serialise an internal Survey to a platform-specific format."""
    adapter = _get_adapter(body.format, None, None, None, None)
    try:
        survey = Survey(**body.survey)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid survey payload: {exc}",
        )
    content = adapter.export_survey(survey)
    return ExportResponse(format=body.format, content=content)


@router.post("/create", response_model=CreateResponse)
async def create_survey_endpoint(body: CreateRequest):
    """Create a survey on the target platform or fall back to file export."""
    adapter = _get_adapter(body.format, body.api_url, body.token, body.username, body.password)
    try:
        survey = Survey(**body.survey)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid survey payload: {exc}",
        )

    credentials_present = any([body.api_url, body.token, body.username, body.password])

    if credentials_present and "create" in adapter.capabilities():
        try:
            content = adapter.create_survey(survey)
            created_via = "api" if "api_create" in adapter.capabilities() else "file_export"
        except (ValueError, NotImplementedError):
            content = adapter.export_survey(survey)
            created_via = "file_export"
    else:
        content = adapter.export_survey(survey)
        created_via = "file_export"

    return CreateResponse(format=body.format, platform_id=content, created_via=created_via)
