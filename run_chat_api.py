#!/usr/bin/env python3
"""Startup script for Shape API service."""

import os
from pathlib import Path

import uvicorn

from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.client import LLMClient
from m_shared.session.manager import SessionManager
from shape_api.api import create_app


def main():
    """Initialize and run the Shape API."""

    sessions_base_path = os.getenv("SESSIONS_BASE_PATH", "./data/sessions")
    port = int(os.getenv("CHAT_PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104

    Path(sessions_base_path).mkdir(parents=True, exist_ok=True)

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
