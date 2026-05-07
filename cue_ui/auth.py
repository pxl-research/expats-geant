"""Cookie helpers and OAuth redirect logic for cue_ui."""

import os
import urllib.parse

import httpx
from fastapi import Request

from m_shared.utils.public_url import get_public_url as _public_url

COOKIE_NAME = "autofill_token"

# Server-to-server URL (Docker-internal or localhost)
CUE_API_URL = os.getenv("CUE_API_URL", "http://localhost:8001")

# Browser-accessible URLs (derived from PUBLIC_HOST when not set explicitly)
CUE_PUBLIC_URL = _public_url("CUE_PUBLIC_URL", 8001, default="http://localhost:8001")
CUE_UI_PUBLIC_URL = _public_url("CUE_UI_PUBLIC_URL", 8002, default="http://localhost:8002")

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
    issuer_url = os.getenv("OIDC_ISSUER_URL", "http://localhost:8080/realms/expats")
    client_id = os.getenv("OIDC_CLIENT_ID", "cue-api")
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
    keycloak_public_url = (_public_url("KEYCLOAK_PUBLIC_URL", 8080) or "").rstrip("/")
    if keycloak_public_url:
        internal_base = issuer_url.split("/realms/")[0].rstrip("/")
        end_session_endpoint = end_session_endpoint.replace(internal_base, keycloak_public_url, 1)
    params = {"client_id": client_id}
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri
    return f"{end_session_endpoint}?{urllib.parse.urlencode(params)}"


def require_auth(request: Request) -> str:
    """FastAPI dependency: return token or redirect to login."""
    token = get_token(request)
    if not token:
        raise _AuthRedirect()
    return token


class _AuthRedirect(Exception):
    """Sentinel used by middleware to trigger login redirect."""
