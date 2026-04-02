"""Shape UI: authentication routes."""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from shape_ui.auth import (
    MCHAT_API_URL,
    MCHAT_PUBLIC_URL,
    SHAPE_UI_PUBLIC_URL,
    clear_token_cookie,
    get_logout_url,
    set_token_cookie,
)
from shape_ui.router import templates

router = APIRouter()


@router.get("/auth/login")
async def auth_login():
    """Redirect browser to Shape OIDC login (public URL, browser-accessible)."""
    return RedirectResponse(url=f"{MCHAT_PUBLIC_URL}/auth/login")


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    token: str | None = None,
):
    """Handle OIDC callback: proxy code+state to Shape server-side, set cookie."""
    if token:
        response = RedirectResponse(url="/", status_code=302)
        set_token_cookie(response, token)
        return response

    if code and state:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{MCHAT_API_URL}/auth/callback",
                    params={"code": code, "state": state},
                    follow_redirects=False,
                )
            resp.raise_for_status()
            jwt_token = resp.json().get("token")
        except Exception:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"message": "Authentication failed: could not exchange code for token."},
                status_code=502,
            )
        if not jwt_token:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"message": "Authentication failed: no token in response."},
                status_code=502,
            )
        response = RedirectResponse(url="/", status_code=302)
        set_token_cookie(response, jwt_token)
        return response

    return templates.TemplateResponse(
        request,
        "error.html",
        {"message": "Authentication failed: no token or authorization code received."},
        status_code=400,
    )


@router.get("/auth/logout")
async def auth_logout():
    """Clear auth cookie and end the OIDC session at the provider."""
    logout_url = await get_logout_url(post_logout_redirect_uri=SHAPE_UI_PUBLIC_URL)
    response = RedirectResponse(url=logout_url, status_code=302)
    clear_token_cookie(response)
    return response
