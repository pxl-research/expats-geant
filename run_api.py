#!/usr/bin/env python3
"""Startup script for M-Autofill API service."""

import os
import sys
from pathlib import Path

import uvicorn

from m_shared.session.manager import SessionManager
from m_shared.llm.client import LLMClient
from m_shared.utils.audit import AuditLogger
from m_shared.auth.middleware import SessionMiddleware
from m_autofill.api import create_app


def main():
    """Initialize and run the M-Autofill API."""
    
    # Configuration from environment
    sessions_base_path = os.getenv("SESSIONS_BASE_PATH", "./data/sessions")
    chroma_base_path = os.getenv("CHROMA_BASE_PATH", "./data/chroma")
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Create base directories
    Path(sessions_base_path).mkdir(parents=True, exist_ok=True)
    Path(chroma_base_path).mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    print("Initializing M-Autofill service...")
    
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
    
    # Audit logger
    audit_logger = AuditLogger(base_path=sessions_base_path)
    print("✓ AuditLogger initialized")
    
    # Create FastAPI app
    app = create_app(
        session_manager=session_manager,
        llm_client=llm_client,
        audit_logger=audit_logger,
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    )
    
    # Add session middleware
    app.add_middleware(
        SessionMiddleware,
        session_manager=session_manager,
        ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "24"))
    )
    
    print("✓ FastAPI app configured")
    print(f"\nStarting server on {host}:{port}...")
    print(f"API docs available at: http://{host}:{port}/docs\n")
    
    # Run server
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
