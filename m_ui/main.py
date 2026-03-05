"""FastAPI app factory for M-UI survey review frontend."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from m_ui.router import router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the M-UI FastAPI application."""
    app = FastAPI(
        title="M-UI",
        description="Survey review frontend for M-Autofill",
        version="0.1.0",
    )

    # Mount static files
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("m_ui.main:app", host=host, port=port, reload=False)
