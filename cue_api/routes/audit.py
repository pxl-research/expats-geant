"""Cue API: audit report routes."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, Response

from cue_api.models import AuditDeleteResponse
from m_shared.utils.audit import AuditEventType

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_audit_plaintext(report, session_id: str) -> str:
    """Render an AuditReport as a human-readable plaintext string."""
    doc_entries = [e for e in report.log_entries if e.event_type == AuditEventType.UPLOAD]
    sug_entries = [e for e in report.log_entries if e.event_type == AuditEventType.SUGGEST]
    n_docs = report.summary.get("documents_uploaded", len(doc_entries))
    n_sugs = report.summary.get("suggestions_generated", len(sug_entries))
    n_edits = report.summary.get("suggestions_edited", 0)
    source_counts = [e.details.get("source_count", 0) for e in sug_entries]
    avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0.0

    plaintext = f"""AUDIT REPORT — Session {session_id}
Created: {report.created_at}
Ended: {report.ended_at or 'N/A'}

DOCUMENTS UPLOADED ({n_docs}):
"""
    for entry in doc_entries:
        d = entry.details
        plaintext += f"- {d.get('filename')} ({d.get('file_size', 0):,} bytes) — uploaded {entry.timestamp}\n"

    plaintext += f"\nSUGGESTIONS GENERATED ({n_sugs}):\n"
    for i, entry in enumerate(sug_entries, 1):
        s = entry.details
        plaintext += f"[{i}] Question: {s.get('question')}\n"
        plaintext += f"    Suggestion: {str(s.get('suggested_answer', ''))[:100]}...\n"
        plaintext += f"    Sources: {', '.join(s.get('sources_used', []))}\n"
        plaintext += f"    Generated: {entry.timestamp}\n"
        plaintext += "\n"

    plaintext += f"""SUMMARY:
- Total Documents: {n_docs}
- Total Suggestions: {n_sugs}
- Total Edits: {n_edits}
- Avg Sources per Suggestion: {avg_sources:.1f}
"""
    return plaintext


@router.get("/audit-report")
async def get_audit_report(
    request: Request,
    format: str = "json",
):
    """Retrieve session audit report."""
    audit_logger = request.app.state.audit_logger
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit logging not enabled",
        )

    session = request.state.session

    if audit_logger.is_deleted(session.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit report has been deleted (erasure request honoured)",
        )

    try:
        report = audit_logger.generate_report(session.session_id)

        if format == "plaintext":
            return PlainTextResponse(content=_format_audit_plaintext(report, session.session_id))
        else:
            return report

    except Exception:
        logger.exception("Failed to generate audit report for session %s", session.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed",
        )


@router.get("/answer-report/download")
async def download_answer_report(request: Request):
    """Return the session's answer report as a downloadable JSON file."""
    from cue_api.routes.suggestions import _get_report_lock

    session = request.state.session
    session_manager = request.app.state.session_manager
    session_path = session_manager._get_session_path(session.session_id)
    report_path = session_path / "answer_report.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No suggestions have been generated yet",
        )

    def _read():
        with _get_report_lock(session_path):
            return [
                json.loads(line)
                for line in report_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    data = await asyncio.to_thread(_read)
    return Response(
        content=json.dumps(data, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="answer_report.json"'},
    )


@router.delete("/audit-report", response_model=AuditDeleteResponse)
async def delete_audit_report(request: Request):
    """Delete the session audit report (GDPR Right to Erasure)."""
    audit_logger = request.app.state.audit_logger
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit logging not enabled",
        )

    session = request.state.session
    audit_logger.delete_report(session.session_id)

    return AuditDeleteResponse(
        session_id=session.session_id,
        deleted=True,
        message="Audit report deleted. No personal data is retained.",
    )
