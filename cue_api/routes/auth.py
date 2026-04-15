"""Cue API: authentication routes."""

import hmac
import os
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.oauth import (
    OIDCConfigurationError,
    OIDCStateError,
    OIDCTokenError,
    exchange_code,
    get_authorization_url,
)
from m_shared.rate_limit import limiter

router = APIRouter()


class TokenRequest(BaseModel):
    user_id: str = Field(max_length=200)
    api_secret: str = Field(max_length=500)


@router.post("/auth/token", tags=["Auth"])
@limiter.limit("10/minute")
async def issue_api_token(request: Request, body: TokenRequest):
    """Issue a JWT for server-to-server callers presenting a shared API secret."""
    expected = os.getenv("API_SECRET", "")
    if not expected or not hmac.compare_digest(body.api_secret, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API secret")
    session_id = uuid.uuid4().hex[:12]
    token = create_token(user_id=body.user_id, session_id=session_id, org="api", roles=["user"])
    return {"token": token, "user_id": body.user_id}


@router.get("/auth/login", tags=["Authentication"])
async def auth_login():
    """Redirect the user to the OIDC provider login page."""
    try:
        authorization_url, _state = await get_authorization_url()
        return RedirectResponse(url=authorization_url, status_code=302)
    except OIDCConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC not configured: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC provider unreachable: {exc}",
        )


@router.get("/auth/callback", tags=["Authentication"])
async def auth_callback(code: str, state: str):
    """Handle OIDC authorization callback and return a platform JWT."""
    try:
        platform_token = await exchange_code(code=code, state=state)
        return {"token": platform_token, "token_type": "bearer"}
    except OIDCStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state: {exc}",
        )
    except OIDCTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID token validation failed: {exc}",
        )
    except OIDCConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC not configured: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC exchange failed: {exc}",
        )
