"""Cue API: session management and privacy routes."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from cue_api.models import (
    SessionDeleteResponse,
    SessionStatsResponse,
    WebConsentRequest,
    WebConsentResponse,
)

router = APIRouter()

_PRIVACY_TEXT = """CUE PRIVACY STATEMENT

DATA COLLECTION:
- Documents you upload are processed temporarily during your session
- Answer suggestions and citations are generated from your documents only
- All processing happens within your isolated session

DATA RETENTION:
- Operational data (documents, vectors, temporary files) deleted when session expires (default: 24-48 hours)
- Audit reports retained for 1 year for compliance, then automatically deleted
- You can delete your session immediately using DELETE /session

DATA USAGE:
- Documents used only for generating answer suggestions
- No profiling, tracking, or cross-session correlation
- No data sharing with third parties

YOUR RIGHTS (GDPR):
- Right to access: Download your audit report anytime (GET /audit-report)
- Right to deletion: Delete your session and data immediately (DELETE /session)
- Right to know: This statement explains all data handling

CONSENT:
By using this service, you consent to:
- Temporary processing of uploaded documents for answer generation
- Storage of audit logs for 1 year for compliance purposes
- LLM processing via OpenRouter (EU-based deployment)

CONTACT:
For privacy concerns: [Insert institutional contact]
For technical issues: [Insert support contact]

Last updated: January 2026
"""


@router.get("/session/stats", response_model=SessionStatsResponse)
async def get_session_stats(request: Request):
    """Get statistics for the current user's session."""
    session = request.state.session
    manager = request.state.session_manager

    stats = manager.get_session_stats(session.session_id)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    stats["web_ingest_enabled"] = bool(getattr(request.app.state, "web_ingest_enabled", False))
    stats["web_consent"] = bool(session.metadata.get("web_consent", False))

    return SessionStatsResponse(**stats)


@router.put("/session/web-consent", response_model=WebConsentResponse)
async def set_web_consent(request: Request, body: WebConsentRequest):
    """Grant or revoke per-session consent for server-side URL fetches."""
    session = request.state.session
    manager = request.state.session_manager
    session.metadata["web_consent"] = bool(body.enabled)
    manager._save_session_metadata(session)
    return WebConsentResponse(web_consent=bool(session.metadata["web_consent"]))


@router.delete("/session", response_model=SessionDeleteResponse)
async def delete_session(request: Request):
    """Delete the current user's session and all associated data (GDPR: forget my data now)."""
    session = request.state.session
    manager = request.state.session_manager

    deleted = manager.delete_session(session.session_id)

    if deleted:
        return SessionDeleteResponse(
            session_id=session.session_id,
            deleted=True,
            message="Session and all data successfully deleted",
        )
    else:
        return SessionDeleteResponse(
            session_id=session.session_id,
            deleted=False,
            message="Session does not exist or was already deleted",
        )


@router.get("/privacy", response_class=PlainTextResponse)
async def get_privacy_statement():
    """Return privacy and GDPR disclosure statement."""
    return _PRIVACY_TEXT
