"""OIDC authentication: discovery, code exchange, token validation, sub normalization."""

import base64
import hashlib
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
from m_shared.utils.public_url import get_public_url

logger = logging.getLogger(__name__)


class OIDCConfigurationError(Exception):
    """Raised when OIDC environment variables are missing or invalid."""


class OIDCStateError(Exception):
    """Raised when OAuth state is missing, invalid, or expired."""


class OIDCTokenError(Exception):
    """Raised when the OIDC ID token fails validation."""


# Module-level state store: state_value -> {expiry, code_verifier, nonce}
# LIMITATION: In-memory dict — not shared across workers or processes.
# For multi-worker deployment, replace with Redis or a shared cache.
# Acceptable for PoC (single-worker uvicorn per container).
_pending_states: dict[str, dict] = {}
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
    redirect_port = int(os.getenv("OIDC_REDIRECT_PORT", "8002"))
    redirect_uri = get_public_url(
        "OIDC_REDIRECT_URI", redirect_port, path="/auth/callback"
    ) or _get_env("OIDC_REDIRECT_URI")
    return (
        _get_env("OIDC_ISSUER_URL"),
        _get_env("OIDC_CLIENT_ID"),
        _get_env("OIDC_CLIENT_SECRET"),
        redirect_uri,
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
    expired = [s for s, data in _pending_states.items() if data["expiry"] < now]
    for s in expired:
        del _pending_states[s]


def _normalize_sub(iss: str, sub: str) -> str:
    """Return a stable, cross-provider user_id from issuer URL and subject claim.

    Example: iss="http://localhost:8080/realms/expats", sub="abc123"
             -> "localhost:8080:abc123"
    """
    parsed = urlparse(iss)
    iss_host = parsed.netloc or parsed.path
    return f"{iss_host}:{sub}"


async def get_logout_url(post_logout_redirect_uri: str | None = None) -> str:
    """Return the OIDC provider's end_session URL.

    Args:
        post_logout_redirect_uri: Where the provider should redirect after logout.

    Returns:
        Full logout URL to redirect the user to.
    """
    issuer_url, client_id, _, _ = _get_oidc_settings()
    discovery = await _fetch_discovery(issuer_url)
    end_session_endpoint = discovery.get("end_session_endpoint")
    if not end_session_endpoint:
        # Fallback for providers without end_session_endpoint
        return post_logout_redirect_uri or "/"

    if post_logout_redirect_uri:
        import urllib.parse

        params = urllib.parse.urlencode(
            {"client_id": client_id, "post_logout_redirect_uri": post_logout_redirect_uri}
        )
        return f"{end_session_endpoint}?{params}"
    return end_session_endpoint


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

    # Rewrite the authorization endpoint hostname for browser-facing redirects.
    # Keycloak's discovery document uses its internal hostname (e.g. http://keycloak:8080),
    # which is unreachable from external browsers. KEYCLOAK_PUBLIC_URL replaces the base.
    keycloak_public_url = (get_public_url("KEYCLOAK_PUBLIC_URL", 8080) or "").rstrip("/")
    if keycloak_public_url:
        internal_base = issuer_url.split("/realms/")[0].rstrip("/")
        authorization_endpoint = authorization_endpoint.replace(
            internal_base, keycloak_public_url, 1
        )

    state = str(uuid4())
    nonce = str(uuid4())

    # PKCE: generate code_verifier and S256 code_challenge
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    _purge_expired_states()
    _pending_states[state] = {
        "expiry": time.time() + _STATE_TTL_SECONDS,
        "code_verifier": code_verifier,
        "nonce": nonce,
    }

    import urllib.parse

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": used_redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorization_url = f"{authorization_endpoint}?{params}"
    return authorization_url, state


async def exchange_code(
    code: str,
    state: str,
    redirect_uri: str | None = None,
    tenant_registry=None,
) -> str:
    """Exchange an authorization code for a platform JWT.

    Validates the CSRF state, calls the token endpoint, validates the ID token,
    extracts the subject claim, and issues a platform JWT via create_token().

    Args:
        code: Authorization code from the OIDC callback query parameter.
        state: State value from the OIDC callback query parameter.
        redirect_uri: Override the OIDC_REDIRECT_URI env var (optional).
        tenant_registry: Optional TenantRegistry for resolving org from groups claim.

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

    # Validate state and retrieve PKCE/nonce data (atomic pop to avoid race)
    _purge_expired_states()
    state_data = _pending_states.pop(state, None)
    if state_data is None:
        logger.warning("OIDC callback rejected: invalid or expired state parameter")
        raise OIDCStateError("Invalid or expired OAuth state parameter.")
    code_verifier = state_data["code_verifier"]
    expected_nonce = state_data["nonce"]

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
                    "code_verifier": code_verifier,
                },
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OIDC token endpoint returned HTTP %s: %s",
                exc.response.status_code,
                exc,
            )
            raise
        except httpx.TransportError as exc:
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

    # Verify issuer matches configured OIDC provider (OIDC spec requirement).
    # When KEYCLOAK_PUBLIC_URL rewrites the hostname, the ID token's issuer uses the
    # public URL while OIDC_ISSUER_URL uses the Docker-internal URL — both are valid.
    token_iss = claims.get("iss")
    keycloak_public_url = (get_public_url("KEYCLOAK_PUBLIC_URL", 8080) or "").rstrip("/")
    if keycloak_public_url:
        internal_base = issuer_url.split("/realms/")[0].rstrip("/")
        expected_public_issuer = issuer_url.replace(internal_base, keycloak_public_url, 1)
    else:
        expected_public_issuer = None
    if token_iss != issuer_url and token_iss != expected_public_issuer:
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

    # Verify nonce (prevents ID token replay)
    token_nonce = claims.get("nonce")
    if token_nonce != expected_nonce:
        logger.warning("ID token nonce mismatch: got %r, expected %r", token_nonce, expected_nonce)
        raise OIDCTokenError("ID token nonce does not match the expected value.")

    # Extract and normalize subject
    iss = claims.get("iss", issuer_url)
    sub = claims.get("sub")
    if not sub:
        logger.warning("ID token missing required 'sub' claim")
        raise OIDCTokenError("ID token is missing the 'sub' claim.")

    user_id = _normalize_sub(iss, sub)
    session_id = str(uuid4())

    org = "default"
    if tenant_registry:
        for group in claims.get("groups", []):
            group_name = group.lstrip("/")
            if tenant_registry.get_tenant(group_name):
                org = group_name
                break

    platform_token = create_token(
        user_id=user_id,
        session_id=session_id,
        org=org,
    )
    logger.info("OIDC login successful: user_id=%r, org=%r", user_id, org)
    return platform_token
