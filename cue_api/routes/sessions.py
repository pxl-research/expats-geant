"""Cue API: multi-session management routes."""

import os
import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status

from cue_api.models import SessionListItem, SessionListResponse, TransferRequest
from m_shared.auth.jwt_handler import create_token

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse, tags=["Sessions"])
async def list_user_sessions(request: Request):
    """List all active sessions for the authenticated user."""
    user_id = request.state.claims["user_id"]
    manager = request.state.session_manager
    sessions = manager.list_sessions_for_user(user_id)

    items = []
    for s in sessions:
        session_path = manager._get_session_path(s.session_id, user_id=user_id)
        remaining = s.expires_at - datetime.utcnow()
        items.append(
            SessionListItem(
                session_id=s.session_id,
                created_at=s.created_at.isoformat(),
                expires_at=s.expires_at.isoformat(),
                remaining_hours=round(max(0, remaining.total_seconds() / 3600), 2),
                has_survey=(session_path / "survey.json").exists(),
            )
        )

    items.sort(key=lambda it: it.created_at, reverse=True)
    return SessionListResponse(sessions=items)


@router.post("/sessions/new", status_code=201, tags=["Sessions"])
async def create_new_session(request: Request):
    """Create a new session and return a JWT scoped to it."""
    claims = request.state.claims
    user_id = claims["user_id"]
    manager = request.state.session_manager
    ttl_hours = int(os.getenv("SESSION_TTL_HOURS", "24"))

    session = manager.create_session(user_id=user_id, ttl_hours=ttl_hours)
    token = create_token(
        user_id=user_id,
        session_id=session.session_id,
        org=claims.get("org", "default"),
        roles=claims.get("roles", ["respondent"]),
    )
    return {"token": token, "session_id": session.session_id}


@router.post("/sessions/{session_id}/select", tags=["Sessions"])
async def select_session(request: Request, session_id: str):
    """Select/resume an existing session. Returns a new JWT scoped to that session."""
    claims = request.state.claims
    user_id = claims["user_id"]
    manager = request.state.session_manager

    session = manager.get_session(session_id, user_id=user_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    token = create_token(
        user_id=user_id,
        session_id=session_id,
        org=claims.get("org", "default"),
        roles=claims.get("roles", ["respondent"]),
    )
    return {"token": token, "session_id": session_id}


@router.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_user_session(request: Request, session_id: str):
    """Delete a session owned by the authenticated user.

    Returns a fresh session-less JWT (`token`) iff the caller's current JWT was
    bound to the deleted session. The client must replace its cookie with this
    token; otherwise the next request would carry a stale `session_id` claim
    that the auth middleware would lazy-resurrect into an empty session shell.
    """
    claims = request.state.claims
    user_id = claims["user_id"]
    manager = request.state.session_manager

    session = manager.get_session(session_id, user_id=user_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    manager.delete_session(session_id, reason="user_request")

    token: str | None = None
    if claims.get("session_id") == session_id:
        token = create_token(
            user_id=user_id,
            session_id=None,
            org=claims.get("org", "default"),
            roles=claims.get("roles", ["respondent"]),
        )

    return {
        "session_id": session_id,
        "deleted": True,
        "message": "Session and all data successfully deleted",
        "token": token,
    }


@router.post("/sessions/{session_id}/transfer", tags=["Sessions"])
async def transfer_session(request: Request, session_id: str, body: TransferRequest):
    """Transfer a session to another user (handoff)."""
    claims = request.state.claims
    user_id = claims["user_id"]
    manager = request.state.session_manager

    session = manager.get_session(session_id, user_id=user_id)
    if not session or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or not owned by you",
        )

    recipient_path = manager._get_user_path(body.recipient_user_id)
    if not recipient_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient user not found (they must have logged in at least once)",
        )

    source_path = manager._get_session_path(session_id, user_id=user_id)
    dest_path = recipient_path / session_id
    if dest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session ID collision at recipient",
        )

    shutil.move(str(source_path), str(dest_path))
    manager._vector_store_cache.pop(session_id, None)

    # Update metadata with new owner
    session = manager._load_session_metadata(session_id, session_path=dest_path)
    if session:
        session.user_id = body.recipient_user_id
        manager._save_session_metadata(session)

    return {"status": "transferred", "session_id": session_id}
