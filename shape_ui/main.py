"""FastAPI app factory for Shape UI survey authoring frontend."""

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from shape_ui.router import router
from shape_ui.routes.auth import router as auth_router
from shape_ui.routes.setup import router as setup_router
from shape_ui.routes.workspace import router as workspace_router


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
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        return response


_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the Shape UI FastAPI application."""
    app = FastAPI(
        title="Shape UI",
        description="Survey authoring frontend for Shape",
        version="0.1.0",
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # Mount static files
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(setup_router)
    app.include_router(workspace_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8004"))
    uvicorn.run("shape_ui.main:app", host=host, port=port, reload=False)
