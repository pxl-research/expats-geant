"""Cue UI router hub: shared helpers, templates, and sub-router registration."""

import os

import markdown as _md  # type: ignore[import-untyped]
import nh3
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router: APIRouter = APIRouter()

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def _markdown_filter(text: str) -> str:
    """Jinja2 filter: render Markdown to sanitized HTML."""
    raw_html = _md.markdown(text or "", extensions=["extra", "nl2br", "tables"])
    return nh3.clean(raw_html)


templates.env.filters["markdown"] = _markdown_filter


def _datefmt_filter(value) -> str:
    """Jinja2 filter: format a datetime or ISO string to '11 May 2026, 14:03 UTC'."""
    if not value:
        return "N/A"
    if isinstance(value, str):
        from datetime import datetime

        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return str(value)
    return value.strftime("%-d %b %Y, %H:%M UTC")


templates.env.filters["datefmt"] = _datefmt_filter

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
