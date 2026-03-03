"""OIDC authentication: discovery, code exchange, token validation, sub normalization."""

import logging
import os
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from authlib.jose import JsonWebKey
from authlib.jose import jwt as authlib_jwt
from authlib.jose.errors import JoseError

from m_shared.auth.jwt_handler import create_token

logger = logging.getLogger(__name__)


class OIDCConfigurationError(Exception):
    """Raised when OIDC environment variables are missing or invalid."""


class OIDCStateError(Exception):
    """Raised when OAuth state is missing, invalid, or expired."""


class OIDCTokenError(Exception):
    """Raised when the OIDC ID token fails validation."""


# Module-level state store: state_value -> expiry timestamp (UTC epoch seconds)
_pending_states: dict[str, float] = {}
_STATE_TTL_SECONDS = 600  # 10 minutes

# Cached OIDC discovery document
_oidc_config: dict | None = None
_jwks_cache: dict | None = None


def _get_env(name: str) -> str:
    """Read a required environment variable or raise OIDCConfigurationError."""
    value = os.getenv(name)
    if not value:
        raise OIDCConfigurationError(
            f"Required environment variable '{name}' is not set. "
            "Set OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, and OIDC_REDIRECT_URI."
        )
    return value


def _get_oidc_settings() -> tuple[str, str, str, str]:
    """Return (issuer_url, client_id, client_secret, redirect_uri)."""
    return (
        _get_env("OIDC_ISSUER_URL"),
        _get_env("OIDC_CLIENT_ID"),
        _get_env("OIDC_CLIENT_SECRET"),
        _get_env("OIDC_REDIRECT_URI"),
    )


async def _fetch_discovery(issuer_url: str) -> dict:
    """Fetch OIDC discovery document from <issuer>/.well-known/openid-configuration."""
    global _oidc_config
    if _oidc_config is not None:
        return _oidc_config

    discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        response = await client.get(discovery_url, timeout=10)
        response.raise_for_status()
        _oidc_config = response.json()
    return _oidc_config


async def _fetch_jwks(jwks_uri: str) -> dict:
    """Fetch JWKS (public keys) from the OIDC provider."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_uri, timeout=10)
        response.raise_for_status()
        _jwks_cache = response.json()
    return _jwks_cache


def _purge_expired_states() -> None:
    """Remove expired state entries from the in-memory store."""
    now = time.time()
    expired = [s for s, exp in _pending_states.items() if exp < now]
    for s in expired:
        del _pending_states[s]


def _normalize_sub(iss: str, sub: str) -> str:
    """Return a stable, cross-provider user_id from issuer URL and subject claim.

    Example: iss="http://localhost:8080/realms/expat-geant", sub="abc123"
             -> "localhost:8080:abc123"
    """
    parsed = urlparse(iss)
    iss_host = parsed.netloc or parsed.path
    return f"{iss_host}:{sub}"


async def get_authorization_url(redirect_uri: str | None = None) -> tuple[str, str]:
    """Build the OIDC authorization URL and generate a CSRF state token.

    Args:
        redirect_uri: Override the OIDC_REDIRECT_URI env var (optional).

    Returns:
        (authorization_url, state) — redirect the user to authorization_url and
        store state for later verification in exchange_code().

    Raises:
        OIDCConfigurationError: If required env vars are missing.
        httpx.HTTPError: If the OIDC discovery endpoint is unreachable.
    """
    issuer_url, client_id, _, env_redirect_uri = _get_oidc_settings()
    used_redirect_uri = redirect_uri or env_redirect_uri

    discovery = await _fetch_discovery(issuer_url)
    authorization_endpoint = discovery["authorization_endpoint"]

    state = str(uuid4())
    _purge_expired_states()
    _pending_states[state] = time.time() + _STATE_TTL_SECONDS

    import urllib.parse

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": used_redirect_uri,
            "scope": "openid email profile",
            "state": state,
        }
    )
    authorization_url = f"{authorization_endpoint}?{params}"
    return authorization_url, state


async def exchange_code(code: str, state: str, redirect_uri: str | None = None) -> str:
    """Exchange an authorization code for a platform JWT.

    Validates the CSRF state, calls the token endpoint, validates the ID token,
    extracts the subject claim, and issues a platform JWT via create_token().

    Args:
        code: Authorization code from the OIDC callback query parameter.
        state: State value from the OIDC callback query parameter.
        redirect_uri: Override the OIDC_REDIRECT_URI env var (optional).

    Returns:
        Platform JWT string (same format as tokens from /dev/token).

    Raises:
        OIDCStateError: If the state is unknown or expired.
        OIDCTokenError: If the ID token is invalid, expired, or has wrong audience.
        OIDCConfigurationError: If required env vars are missing.
        httpx.HTTPError: If the token endpoint is unreachable.
    """
    issuer_url, client_id, client_secret, env_redirect_uri = _get_oidc_settings()
    used_redirect_uri = redirect_uri or env_redirect_uri

    # Validate state
    _purge_expired_states()
    if state not in _pending_states:
        logger.warning("OIDC callback rejected: invalid or expired state parameter")
        raise OIDCStateError("Invalid or expired OAuth state parameter.")
    del _pending_states[state]

    # Fetch discovery document
    discovery = await _fetch_discovery(issuer_url)
    token_endpoint = discovery["token_endpoint"]
    jwks_uri = discovery["jwks_uri"]

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": used_redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("OIDC provider unreachable at token endpoint: %s", exc)
            raise
        token_response = response.json()

    id_token_str = token_response.get("id_token")
    if not id_token_str:
        raise OIDCTokenError("Token endpoint did not return an id_token.")

    # Validate ID token
    jwks_data = await _fetch_jwks(jwks_uri)
    try:
        jwks = JsonWebKey.import_key_set(jwks_data)
        claims = authlib_jwt.decode(id_token_str, jwks)
        claims.validate()
    except JoseError as exc:
        logger.warning("ID token validation failed: %s", exc)
        raise OIDCTokenError(f"ID token validation failed: {exc}") from exc

    # Verify issuer matches configured OIDC provider (OIDC spec requirement)
    token_iss = claims.get("iss")
    if token_iss != issuer_url:
        logger.warning("ID token issuer mismatch: got %r, expected %r", token_iss, issuer_url)
        raise OIDCTokenError(
            f"ID token issuer {token_iss!r} does not match configured issuer {issuer_url!r}."
        )

    # Verify audience
    aud = claims.get("aud")
    if isinstance(aud, str):
        aud = [aud]
    if client_id not in (aud or []):
        logger.warning("ID token audience mismatch: got %r, expected client_id %r", aud, client_id)
        raise OIDCTokenError(f"ID token audience {aud!r} does not contain client_id '{client_id}'.")

    # Extract and normalize subject
    iss = claims.get("iss", issuer_url)
    sub = claims.get("sub")
    if not sub:
        logger.warning("ID token missing required 'sub' claim")
        raise OIDCTokenError("ID token is missing the 'sub' claim.")

    user_id = _normalize_sub(iss, sub)
    session_id = str(uuid4())

    platform_token = create_token(
        user_id=user_id,
        session_id=session_id,
        org="default",
    )
    logger.info("OIDC login successful: user_id=%r", user_id)
    return platform_token
