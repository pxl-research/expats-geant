"""FastAPI application factory for Cue answer suggestion service."""

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cue_api.rag_pipeline import RAGPipeline
from cue_api.routes.audit import router as audit_router
from cue_api.routes.auth import router as auth_router
from cue_api.routes.documents import router as documents_router
from cue_api.routes.extract_form import router as extract_form_router
from cue_api.routes.review_state import router as review_state_router
from cue_api.routes.session import router as session_router
from cue_api.routes.sessions import router as sessions_router
from cue_api.routes.suggestions import router as suggestions_router
from cue_api.routes.surveys import router as surveys_router
from cue_api.routes.web import router as web_router
from m_shared.llm.client import LLMClient
from m_shared.rate_limit import apply_rate_limiting
from m_shared.routes.admin import router as admin_router
from m_shared.session.manager import SessionManager
from m_shared.utils.audit import AuditLogger

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSION_SCHEMES = ("chrome-extension://", "moz-extension://")


def _parse_extension_origins(raw: str) -> list[str]:
    """Parse EXTENSION_ALLOWED_ORIGINS into an exact-match origin list.

    Drops empty entries, entries containing wildcards, and entries that do not
    start with an allowed extension scheme. Rejected entries are warn-logged
    once at startup so misconfiguration is visible.
    """
    accepted: list[str] = []
    for entry in raw.split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        if "*" in candidate:
            logger.warning("EXTENSION_ALLOWED_ORIGINS: rejected wildcard entry '%s'", candidate)
            continue
        if not candidate.startswith(_ALLOWED_EXTENSION_SCHEMES):
            logger.warning(
                "EXTENSION_ALLOWED_ORIGINS: rejected entry '%s' (only %s permitted)",
                candidate,
                ", ".join(_ALLOWED_EXTENSION_SCHEMES),
            )
            continue
        accepted.append(candidate)
    return accepted


def create_app(
    session_manager: SessionManager,
    llm_client: LLMClient | None = None,
    audit_logger: AuditLogger | None = None,
    max_file_size_mb: int = 50,
    lifespan=None,
) -> FastAPI:
    """Create FastAPI application with Cue endpoints.

    Args:
        session_manager: SessionManager instance
        llm_client: LLM client for answer generation (optional for session-only endpoints)
        audit_logger: Audit logger for compliance tracking
        max_file_size_mb: Maximum file size in MB (default: 50)
        lifespan: Optional AsyncContextManager for startup/shutdown hooks (e.g. cleanup job)

    Returns:
        Configured FastAPI app
    """
    _is_production = os.getenv("ENVIRONMENT") == "production"
    app = FastAPI(
        title="Cue API",
        description="Evidence-based answer suggestion service",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if _is_production else "/docs",
        redoc_url=None if _is_production else "/redoc",
        openapi_url=None if _is_production else "/openapi.json",
    )

    apply_rate_limiting(app)

    extension_origins = _parse_extension_origins(os.getenv("EXTENSION_ALLOWED_ORIGINS", ""))
    if extension_origins:
        logger.info("CORS: allowing extension origins: %s", extension_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=extension_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_cache_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    # Initialize RAG pipeline if LLM client provided
    rag_pipeline = None
    if llm_client:
        try:
            max_citation_distance = max(0.0, float(os.getenv("CUE_MAX_CITATION_DISTANCE", "1.8")))
        except ValueError:
            logger.warning("Invalid CUE_MAX_CITATION_DISTANCE value; using default 1.8")
            max_citation_distance = 1.8
        query_rewrite = os.getenv("CUE_QUERY_REWRITE", "true").lower() != "false"
        try:
            rewrite_batch_size = max(1, int(os.getenv("CUE_REWRITE_BATCH_SIZE", "20")))
        except ValueError:
            logger.warning("Invalid CUE_REWRITE_BATCH_SIZE; using default 20")
            rewrite_batch_size = 20
        rewrite_llm_client = None
        if query_rewrite:
            rewrite_model = os.getenv("CUE_REWRITE_MODEL") or os.getenv(
                "DEFAULT_LLM_MODEL", "anthropic/claude-haiku-4.5"
            )
            from m_shared.llm import LLMClient as _LLMClient

            try:
                rewrite_llm_client = _LLMClient(model_name=rewrite_model)
            except Exception as e:
                logger.warning("Failed to create rewrite LLM client: %s; using main client", e)
        rag_pipeline = RAGPipeline(
            session_manager=session_manager,
            llm_client=llm_client,
            audit_logger=audit_logger,
            max_citation_distance=max_citation_distance,
            query_rewrite=query_rewrite,
            rewrite_batch_size=rewrite_batch_size,
            rewrite_llm_client=rewrite_llm_client,
        )

    # Store dependencies on app.state for route modules
    app.state.session_manager = session_manager
    app.state.llm_client = llm_client
    app.state.audit_logger = audit_logger
    app.state.rag_pipeline = rag_pipeline
    app.state.max_file_size_mb = max_file_size_mb
    app.state.web_ingest_enabled = os.getenv("CUE_WEB_INGEST_ENABLED", "false").lower() == "true"

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
        )

    @app.get("/")
    async def root():
        return {"service": "cue-api", "status": "running"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    app.include_router(auth_router)
    app.include_router(session_router)
    app.include_router(sessions_router)
    app.include_router(documents_router)
    app.include_router(suggestions_router)
    app.include_router(audit_router)
    app.include_router(review_state_router)
    app.include_router(surveys_router)
    app.include_router(web_router)
    app.include_router(extract_form_router)
    app.include_router(admin_router)

    return app
