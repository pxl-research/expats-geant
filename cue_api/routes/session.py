"""Cue API: session management and privacy routes."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from cue_api.models import (
    RemoveSourceResponse,
    SessionDeleteResponse,
    SessionStatsResponse,
    WebConsentRequest,
    WebConsentResponse,
)
from m_shared.vectordb.utils import clean_up_string

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


@router.delete("/session/documents/{name}", response_model=RemoveSourceResponse)
async def remove_session_document(request: Request, name: str):
    """Remove a single source (collection) from the current session.

    The path parameter is sanitised through the same helper used at ingest time;
    the resulting collection name is looked up in the session's vector store and
    deleted entirely. Idempotent: a second call for the same name returns 404.
    Cached suggestions citing the removed source are left untouched by design —
    users refresh via the existing Regenerate path if they want suggestions
    recomputed against the trimmed source set.
    """
    session = request.state.session
    claims = getattr(request.state, "claims", {}) or {}
    manager = request.state.session_manager
    audit_logger = getattr(request.app.state, "audit_logger", None)

    collection_name = clean_up_string(name)
    if not collection_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty or invalid source name",
        )

    try:
        store = manager.get_vector_store(session.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        ) from exc

    if collection_name not in set(store.list_documents()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {name!r} not found in this session",
        )

    source_kind: str | None = None
    source_mime: str | None = None
    try:
        col = store.cdb_client.get_collection(collection_name)
        metadatas = col.get(include=["metadatas"]).get("metadatas") or []
        first_meta = next((m for m in metadatas if m), {}) or {}
        source_kind = first_meta.get("source_kind")
        source_mime = first_meta.get("source_mime")
    except Exception:  # noqa: S110 - best-effort provenance capture
        pass

    store.remove_document(collection_name)

    if audit_logger:
        audit_logger.log_source_removed(
            session_id=session.session_id,
            name=collection_name,
            source_kind=source_kind,
            source_mime=source_mime,
            user_id=claims.get("user_id"),
        )

    return RemoveSourceResponse(status="ok", name=collection_name)


@router.get("/privacy", response_class=PlainTextResponse)
async def get_privacy_statement():
    """Return privacy and GDPR disclosure statement."""
    return _PRIVACY_TEXT
