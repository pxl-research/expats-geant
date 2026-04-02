"""Shape UI router hub: shared helpers, templates, and sub-router registration."""

import os

import markdown as _md  # type: ignore[import-untyped]
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router: APIRouter = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def _markdown_filter(text: str) -> str:
    """Jinja2 filter: render markdown to HTML (used in message bubbles)."""
    return _md.markdown(text or "", extensions=["extra", "nl2br"])


templates.env.filters["markdown"] = _markdown_filter

ADAPTER_CAPABILITIES = {
    "lss": {"label": "LimeSurvey", "push": True},
    "limesurvey": {"label": "LimeSurvey", "push": True},
    "qsf": {"label": "Qualtrics", "push": True},
    "qualtrics": {"label": "Qualtrics", "push": True},
    "sm": {"label": "SurveyMonkey", "push": False},
    "surveymonkey": {"label": "SurveyMonkey", "push": False},
    "qti": {"label": "QTI", "push": False},
}

EXPORT_FORMATS = [
    {"id": "lss", "label": "LimeSurvey", "push": True},
    {"id": "qsf", "label": "Qualtrics", "push": True},
    {"id": "sm", "label": "SurveyMonkey", "push": False},
    {"id": "qti", "label": "QTI", "push": False},
]


def _render_error(request: Request, message: str, status_code: int = 500) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": message},
        status_code=status_code,
    )


@router.get("/health")
async def health():
    return {"status": "healthy"}


# Import and include sub-routers (after shared objects are defined)
from shape_ui.routes.auth import router as auth_router  # noqa: E402
from shape_ui.routes.setup import router as setup_router  # noqa: E402
from shape_ui.routes.workspace import router as workspace_router  # noqa: E402

router.include_router(auth_router)
router.include_router(setup_router)
router.include_router(workspace_router)
