"""Cookie helpers and OAuth redirect logic for m_chat_ui."""

import os

from fastapi import Request

COOKIE_NAME = "chat_token"

# Server-to-server URL (Docker-internal or localhost)
MCHAT_API_URL = os.getenv("MCHAT_API_URL", "http://localhost:8003")

# Browser-accessible URL for OAuth redirects (must be reachable by the end user's browser)
MCHAT_PUBLIC_URL = os.getenv("MCHAT_PUBLIC_URL", "http://localhost:8003")

# Set COOKIE_SECURE=true in production (HTTPS deployments)
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


def get_token(request: Request) -> str | None:
    """Read JWT from HttpOnly cookie."""
    return request.cookies.get(COOKIE_NAME)


def set_token_cookie(response, token: str) -> None:
    """Write JWT to secure HttpOnly cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=86400,  # 24 hours
    )


def clear_token_cookie(response) -> None:
    """Remove auth cookie."""
    response.delete_cookie(key=COOKIE_NAME)
