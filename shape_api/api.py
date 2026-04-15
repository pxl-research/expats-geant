"""FastAPI application factory for Shape survey transform and tool endpoints."""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from m_shared.rate_limit import apply_rate_limiting
from m_shared.session.manager import SessionManager
from shape_api.routes.auth import router as auth_router
from shape_api.routes.chat import router as chat_router
from shape_api.routes.tools import router as tools_router
from shape_api.routes.transforms import router as transforms_router


def create_app(
    session_manager: SessionManager,
    llm_client=None,
    adapter_registry=None,
) -> FastAPI:
    """Create the Shape FastAPI application.

    Args:
        session_manager: SessionManager for auth session handling.
        llm_client: Optional LLM client for tool endpoints (suggest, tag).
        adapter_registry: Unused; reserved for future extensibility.

    Returns:
        Configured FastAPI application.
    """
    _is_production = os.getenv("ENVIRONMENT") == "production"
    app = FastAPI(
        title="Shape API",
        description="Survey transform and AI tool endpoints",
        version="0.1.0",
        docs_url=None if _is_production else "/docs",
        redoc_url=None if _is_production else "/redoc",
        openapi_url=None if _is_production else "/openapi.json",
    )

    apply_rate_limiting(app)

    @app.middleware("http")
    async def add_cache_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    # Store dependencies on app.state for route modules
    app.state.session_manager = session_manager
    app.state.llm_client = llm_client

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.get("/")
    async def root():
        return {"service": "shape-api", "status": "running"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    app.include_router(auth_router)
    app.include_router(transforms_router)
    app.include_router(tools_router)
    app.include_router(chat_router)

    return app
