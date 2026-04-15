"""FastAPI app factory for Cue UI survey review frontend."""

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from cue_ui.router import router
from cue_ui.routes.auth import router as auth_router
from cue_ui.routes.review import router as review_router
from cue_ui.routes.upload import router as upload_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        return response


_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the Cue UI FastAPI application."""
    app = FastAPI(
        title="Cue UI",
        description="Survey review frontend for Cue",
        version="0.1.0",
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # Mount static files
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(upload_router)
    app.include_router(review_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("cue_ui.main:app", host=host, port=port, reload=False)
