#!/usr/bin/env python3
"""Startup script for Cue API service."""

import asyncio
import logging
import logging.handlers
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

from cue_api.api import create_app
from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.client import LLMClient
from m_shared.session.manager import SessionManager
from m_shared.tenant import TenantRegistry
from m_shared.utils.audit import AuditLogger
from m_shared.utils.startup_checks import check_secrets

logger = logging.getLogger(__name__)


class ScheduledCleanupRunner:
    """Periodically invokes SessionManager.cleanup_expired_sessions().

    Runs as an asyncio background task alongside the FastAPI server. The loop
    sleeps first, then cleans up — so a freshly started server won't trigger
    cleanup immediately on startup.

    Usage (via lifespan, see main() below):
        runner = ScheduledCleanupRunner(session_manager, interval_minutes=60)
        runner.start()   # call inside lifespan startup
        ...
        runner.stop()    # call inside lifespan shutdown
    """

    def __init__(self, session_manager: SessionManager, interval_minutes: int = 60):
        self.session_manager = session_manager
        self.interval_seconds = interval_minutes * 60
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        """Background loop: sleep for the interval, then clean up expired sessions."""
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                deleted = self.session_manager.cleanup_expired_sessions()
                if deleted:
                    logger.info("Cleanup job: removed %d expired session(s)", len(deleted))
                else:
                    logger.debug("Cleanup job: no expired sessions found")
            except Exception as e:
                # Log and continue — a failed cleanup run should not crash the API
                logger.error("Cleanup job failed: %s", e)

    def start(self) -> None:
        """Schedule the cleanup loop as an asyncio background task."""
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the background task and await its termination."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


def main():
    """Initialize and run the Cue API."""

    check_secrets()

    # Configuration from environment
    sessions_base_path = os.getenv("SESSIONS_BASE_PATH", "./data/sessions")
    chroma_base_path = os.getenv("CHROMA_BASE_PATH", "./data/chroma")
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104 - intentional, overridable via env
    cleanup_interval = int(os.getenv("CLEANUP_JOB_INTERVAL_MINUTES", "60"))

    # Create base directories
    Path(sessions_base_path).mkdir(parents=True, exist_ok=True)
    Path(chroma_base_path).mkdir(parents=True, exist_ok=True)

    # Security event log — rotating file, INFO+ from auth layer only
    Path("logs").mkdir(exist_ok=True)
    _security_handler = logging.handlers.RotatingFileHandler(
        "logs/security.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    _security_handler.setLevel(logging.INFO)
    _security_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger("m_shared.auth").setLevel(logging.INFO)
    logging.getLogger("m_shared.auth").addHandler(_security_handler)

    # Initialize components
    print("Initializing Cue service...")

    session_manager = SessionManager(base_path=sessions_base_path)
    print(f"✓ SessionManager initialized (base: {sessions_base_path})")

    # LLM client (optional - some endpoints work without it)
    llm_client = None
    if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        try:
            llm_client = LLMClient()
            print("✓ LLM client initialized")
        except Exception as e:
            print(f"⚠ LLM client initialization failed: {e}")
            print("  Suggestion endpoints will not work")
    else:
        print("⚠ No LLM API key found (set OPENROUTER_API_KEY or OPENAI_API_KEY)")
        print("  Suggestion endpoints will not work")

    # Tenant registry (optional — single-tenant mode when not configured)
    tenant_registry = None
    registry_path = os.getenv("TENANT_REGISTRY_PATH", "")
    if registry_path:
        encryption_key = os.getenv("TENANT_ENCRYPTION_KEY", "")
        tenant_registry = TenantRegistry(encryption_key=encryption_key or None)
        tenant_registry.load(registry_path)
        print(f"✓ Tenant registry loaded ({len(tenant_registry)} tenant(s))")
    else:
        print("ℹ No tenant registry configured — single-tenant mode")

    # Build LLM client pool (default + per-tenant)
    llm_client_pool: dict[str, LLMClient] = {}
    if llm_client:
        llm_client_pool["default"] = llm_client
        llm_client_pool["api"] = llm_client
    if tenant_registry and llm_client:
        for slug in tenant_registry.slugs:
            tenant = tenant_registry.get_tenant(slug)
            try:
                llm_client_pool[slug] = LLMClient(
                    api_key=tenant.api_key,
                    base_url=tenant.base_url,
                )
                print(f"  ✓ LLM client for tenant '{slug}'")
            except Exception as e:
                print(f"  ⚠ LLM client for tenant '{slug}' failed: {e}")

    # Audit logger
    audit_logger = AuditLogger(base_path=sessions_base_path)
    print("✓ AuditLogger initialized")

    # Background cleanup job
    cleanup_runner = ScheduledCleanupRunner(session_manager, interval_minutes=cleanup_interval)

    @asynccontextmanager
    async def lifespan(app):
        # Startup: launch background cleanup task
        cleanup_runner.start()
        print(f"✓ Cleanup job started (interval: {cleanup_interval}m)")
        yield
        # Shutdown: cancel background task cleanly
        await cleanup_runner.stop()
        print("✓ Cleanup job stopped")

    # Create FastAPI app
    app = create_app(
        session_manager=session_manager,
        llm_client=llm_client,
        audit_logger=audit_logger,
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
        lifespan=lifespan,
    )

    # Attach tenant infrastructure to app state
    app.state.tenant_registry = tenant_registry
    app.state.llm_client_pool = llm_client_pool or None

    # Add session middleware
    app.add_middleware(
        SessionMiddleware,
        session_manager=session_manager,
        ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "24")),
    )

    print("✓ FastAPI app configured")
    print(f"\nStarting server on {host}:{port}...")
    print(f"API docs available at: http://{host}:{port}/docs\n")

    # Run server
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
