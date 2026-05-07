"""Cookie helpers and OAuth redirect logic for shape_ui."""

import os
import urllib.parse

import httpx
from fastapi import Request


def _public_url(env_var: str, port: int, path: str = "", default: str | None = None) -> str | None:
    value = os.getenv(env_var, "").strip()
    if value:
        return value
    host = os.getenv("PUBLIC_HOST", "").strip()
    if host:
        return f"http://{host}:{port}{path}"
    return default


COOKIE_NAME = "chat_token"

# Server-to-server URL (Docker-internal or localhost)
SHAPE_API_URL = os.getenv("SHAPE_API_URL", "http://localhost:8003")

# Browser-accessible URLs (derived from PUBLIC_HOST when not set explicitly)
SHAPE_PUBLIC_URL = _public_url("SHAPE_PUBLIC_URL", 8003, default="http://localhost:8003")
SHAPE_UI_PUBLIC_URL = _public_url("SHAPE_UI_PUBLIC_URL", 8004, default="http://localhost:8004")

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
    keycloak_public_url = (_public_url("KEYCLOAK_PUBLIC_URL", 8080) or "").rstrip("/")
    if keycloak_public_url:
        internal_base = issuer_url.split("/realms/")[0].rstrip("/")
        end_session_endpoint = end_session_endpoint.replace(internal_base, keycloak_public_url, 1)
    params = {"client_id": client_id}
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri
    return f"{end_session_endpoint}?{urllib.parse.urlencode(params)}"
