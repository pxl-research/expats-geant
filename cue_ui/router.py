"""Cue UI router hub: shared helpers, templates, and sub-router registration."""

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

SURVEY_FORMATS = ["qsf", "lss", "qti"]


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
from cue_ui.routes.auth import router as auth_router  # noqa: E402
from cue_ui.routes.review import router as review_router  # noqa: E402
from cue_ui.routes.upload import router as upload_router  # noqa: E402

router.include_router(auth_router)
router.include_router(upload_router)
router.include_router(review_router)
