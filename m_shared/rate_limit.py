"""Shared rate-limiting configuration for all FastAPI applications."""

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


def _key_by_user(request: Request) -> str:
    """Rate-limit key: prefer authenticated user_id, fall back to client IP."""
    claims = getattr(request.state, "claims", None)
    if claims:
        return claims.get("user_id", "anonymous")
    return request.client.host if request.client else "anonymous"


limiter = Limiter(key_func=_key_by_user)


def apply_rate_limiting(app) -> None:
    """Attach slowapi rate limiting middleware and error handler to a FastAPI app."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def reset_limiter() -> None:
    """Disable rate limiting. Intended for test use."""
    limiter.enabled = False
