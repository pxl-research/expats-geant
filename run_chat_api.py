#!/usr/bin/env python3
"""Startup script for Shape API service."""

import logging
import logging.handlers
import os
from pathlib import Path

import uvicorn

from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.client import LLMClient
from m_shared.session.manager import SessionManager
from m_shared.utils.startup_checks import check_secrets
from shape_api.api import create_app


def main():
    """Initialize and run the Shape API."""

    check_secrets()

    sessions_base_path = os.getenv("SESSIONS_BASE_PATH", "./data/sessions")
    port = int(os.getenv("CHAT_PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104

    Path(sessions_base_path).mkdir(parents=True, exist_ok=True)

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

    print("Initializing Shape service...")

    session_manager = SessionManager(base_path=sessions_base_path)
    print(f"✓ SessionManager initialized (base: {sessions_base_path})")

    llm_client = None
    if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        try:
            llm_client = LLMClient()
            print("✓ LLM client initialized")
        except Exception as e:
            print(f"⚠ LLM client initialization failed: {e}")
            print("  Tool endpoints (suggest, validate LLM tier, tag) will not work")
    else:
        print("⚠ No LLM API key found (set OPENROUTER_API_KEY or OPENAI_API_KEY)")
        print("  Tool endpoints (suggest, validate LLM tier, tag) will not work")

    app = create_app(session_manager=session_manager, llm_client=llm_client)
    app.add_middleware(
        SessionMiddleware,
        session_manager=session_manager,
        ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "24")),
    )

    print("✓ FastAPI app configured")
    print(f"\nStarting server on {host}:{port}...")
    print(f"API docs available at: http://localhost:{port}/docs\n")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
