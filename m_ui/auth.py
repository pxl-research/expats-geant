"""Cookie helpers and OAuth redirect logic for m_ui."""

import os

from fastapi import Request

COOKIE_NAME = "autofill_token"

# Server-to-server URL (Docker-internal or localhost)
AUTOFILL_API_URL = os.getenv("AUTOFILL_API_URL", "http://localhost:8001")

# Browser-accessible URL for OAuth redirects (must be reachable by the end user's browser)
AUTOFILL_PUBLIC_URL = os.getenv("AUTOFILL_PUBLIC_URL", "http://localhost:8001")


def get_token(request: Request) -> str | None:
    """Read JWT from HttpOnly cookie."""
    return request.cookies.get(COOKIE_NAME)


def set_token_cookie(response, token: str) -> None:
    """Write JWT to secure HttpOnly cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Set True in production (HTTPS)
        samesite="lax",
        max_age=86400,  # 24 hours
    )


def clear_token_cookie(response) -> None:
    """Remove auth cookie."""
    response.delete_cookie(key=COOKIE_NAME)


def require_auth(request: Request) -> str:
    """FastAPI dependency: return token or redirect to login."""
    token = get_token(request)
    if not token:
        raise _AuthRedirect()
    return token


class _AuthRedirect(Exception):
    """Sentinel used by middleware to trigger login redirect."""
