"""Cookie helpers and OAuth redirect logic for shape_ui."""

import os
import urllib.parse

import httpx
from fastapi import Request

COOKIE_NAME = "chat_token"

# Server-to-server URL (Docker-internal or localhost)
SHAPE_API_URL = os.getenv("SHAPE_API_URL", "http://localhost:8003")

# Browser-accessible URL for OAuth redirects (must be reachable by the end user's browser)
SHAPE_PUBLIC_URL = os.getenv("SHAPE_PUBLIC_URL", "http://localhost:8003")

# Public base URL of this UI (used as post-logout redirect target)
SHAPE_UI_PUBLIC_URL = os.getenv("SHAPE_UI_PUBLIC_URL", "http://localhost:8004")

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


async def get_logout_url(post_logout_redirect_uri: str | None = None) -> str:
    """Return the OIDC provider end_session URL for single sign-out."""
    issuer_url = os.getenv("OIDC_ISSUER_URL", "http://keycloak:8080/realms/expats")
    client_id = os.getenv("OIDC_CLIENT_ID", "shape-api")
    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(discovery_url, timeout=5)
            resp.raise_for_status()
            end_session_endpoint = resp.json().get("end_session_endpoint")
    except Exception:
        return post_logout_redirect_uri or "/"
    if not end_session_endpoint:
        return post_logout_redirect_uri or "/"
    params = {"client_id": client_id}
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri
    return f"{end_session_endpoint}?{urllib.parse.urlencode(params)}"
