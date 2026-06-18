"""JWT token creation and validation for session-based authentication."""

import logging
import os
from datetime import UTC, datetime, timedelta

import jwt

logger = logging.getLogger(__name__)

_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512"}
_MAX_TOKEN_LENGTH = 8192


class TokenError(Exception):
    """Base exception for token-related errors."""

    pass


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""

    pass


class TokenInvalidError(TokenError):
    """Raised when a token is invalid or tampered with."""

    pass


def create_token(
    user_id: str,
    session_id: str | None = None,
    org: str = "default",
    roles: list[str] | None = None,
    expiration_hours: int | None = None,
) -> str:
    """
    Create a signed JWT token for authenticated access.

    Args:
        user_id: Unique identifier for the user
        session_id: Session identifier (None for session-list-only tokens)
        org: Organization identifier for multi-tenancy
        roles: List of user roles (e.g., ["respondent"], ["administrator"])
        expiration_hours: Token validity period in hours (defaults to JWT_EXPIRATION_HOURS env var or 24)

    Returns:
        Signed JWT token string

    Raises:
        ValueError: If JWT_SECRET environment variable is not set
    """
    secret = os.getenv("JWT_SECRET")
    if not secret:
        logger.error("Token creation failed: JWT_SECRET environment variable is not set")
        raise ValueError("JWT_SECRET environment variable must be set")

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise ValueError(f"JWT_ALGORITHM must be one of {_ALLOWED_ALGORITHMS}, got '{algorithm}'")
    if expiration_hours is None:
        expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

    if roles is None:
        roles = ["respondent"]

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=expiration_hours)

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "org": org,
        "roles": roles,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


def validate_token(token: str) -> dict:
    """
    Verify JWT token signature, expiration, and extract claims.

    Args:
        token: JWT token string (typically from Authorization: Bearer <token> header)

    Returns:
        Dictionary containing token claims (user_id, session_id, org, roles)

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token signature is invalid or tampered with
        ValueError: If JWT_SECRET environment variable is not set

    Example:
        >>> try:
        ...     claims = validate_token(token)
        ...     user_id = claims["user_id"]
        ...     session_id = claims["session_id"]
        ... except TokenExpiredError:
        ...     # Return 401 Unauthorized
        ... except TokenInvalidError:
        ...     # Return 401 Unauthorized
    """
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise ValueError("JWT_SECRET environment variable must be set")

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise ValueError(f"JWT_ALGORITHM must be one of {_ALLOWED_ALGORITHMS}, got '{algorithm}'")

    if len(token) > _MAX_TOKEN_LENGTH:
        logger.warning(
            "Token validation failed: length %d exceeds limit %d", len(token), _MAX_TOKEN_LENGTH
        )
        raise TokenInvalidError("Token exceeds maximum allowed length")

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token validation failed: token has expired")
        raise TokenExpiredError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Token validation failed: %s", e)
        raise TokenInvalidError(f"Invalid token: {e}")


def verify_session_access(token_claims: dict, requested_session_id: str) -> bool:
    """
    Enforce session isolation - users can only access their own sessions.

    Args:
        token_claims: Claims extracted from validated token (from validate_token)
        requested_session_id: Session ID the user is attempting to access

    Returns:
        True if access is allowed (session_id matches)

    Raises:
        PermissionError: If user attempts to access another user's session (403 Forbidden)

    Example:
        >>> claims = validate_token(token)
        >>> if not verify_session_access(claims, "session456"):
        ...     # Return 403 Forbidden
    """
    token_session_id = token_claims.get("session_id")
    if token_session_id != requested_session_id:
        raise PermissionError(f"Access denied: Cannot access session {requested_session_id}")
    return True
