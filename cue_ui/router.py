"""Cue UI router hub: shared helpers, templates, and sub-router registration."""

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router: APIRouter = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

SURVEY_FORMATS = ["qsf", "lss", "qti", "sm"]


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
