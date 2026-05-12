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


def _escape_md_table(value: str) -> str:
    """Escape pipe characters for Markdown table cells."""
    return value.replace("|", "\\|")


def _fmt_ts(ts) -> str:
    """Format a datetime for display: '11 May 2026, 14:03 UTC'."""
    if ts is None:
        return "N/A"
    return ts.strftime("%-d %b %Y, %H:%M UTC")


def _format_audit_markdown(report, session_id: str) -> str:
    """Render an AuditReport as a structured Markdown string."""
    doc_entries = [e for e in report.log_entries if e.event_type == AuditEventType.UPLOAD]
    sug_entries = [e for e in report.log_entries if e.event_type == AuditEventType.SUGGEST]
    edit_entries = [e for e in report.log_entries if e.event_type == AuditEventType.EDIT_SUGGESTION]
    n_docs = report.summary.get("documents_uploaded", len(doc_entries))
    n_sugs = report.summary.get("suggestions_generated", len(sug_entries))
    n_edits = report.summary.get("suggestions_edited", len(edit_entries))
    source_counts = [e.details.get("source_count", 0) for e in sug_entries]
    avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0.0

    lines = [
        f"# Audit Report — Session {session_id}",
        "",
        f"**Created:** {_fmt_ts(report.created_at)}  ",
        f"**Ended:** {_fmt_ts(report.ended_at)}  ",
        f"**Retention until:** {_fmt_ts(report.retention_until)}",
        "",
    ]

    # --- Documents ---
    lines.append(f"## Documents Uploaded ({n_docs})")
    lines.append("")
    if doc_entries:
        lines.append("| # | Filename | Size | Uploaded |")
        lines.append("|---|----------|------|----------|")
        for i, entry in enumerate(doc_entries, 1):
            d = entry.details
            fname = _escape_md_table(str(d.get("filename", "")))
            size = f"{d.get('file_size', 0):,} bytes"
            lines.append(f"| {i} | {fname} | {size} | {_fmt_ts(entry.timestamp)} |")
        lines.append("")
    else:
        lines.append("No documents uploaded.")
        lines.append("")

    # --- Suggestions ---
    lines.append(f"## Suggestions Generated ({n_sugs})")
    lines.append("")
    for i, entry in enumerate(sug_entries, 1):
        s = entry.details
        question = s.get("question", "(no question)")
        answer = str(s.get("suggested_answer", ""))[:200]
        lines.append(f"### {i}. {question}")
        lines.append("")
        lines.append(f"- **Suggestion:** {answer}")

        details = s.get("source_details")
        if details:
            lines.append("- **Sources:**")
            for sd in details:
                pos = sd.get("position")
                pos_str = f" ({pos * 100:.1f}%)" if pos is not None else ""
                lines.append(f"    - {sd.get('source', '?')}{pos_str}")
        else:
            sources = ", ".join(s.get("sources_used", []))
            lines.append(f"- **Sources:** {sources or 'none'}")

        lines.append(f"- **Generated:** {_fmt_ts(entry.timestamp)}")
        lines.append("")

    if not sug_entries:
        lines.append("No suggestions generated.")
        lines.append("")

    # --- Edits ---
    if edit_entries:
        lines.append(f"## Edits ({n_edits})")
        lines.append("")
        for i, entry in enumerate(edit_entries, 1):
            d = entry.details
            original = str(d.get("original_suggestion", ""))[:200]
            edited = str(d.get("edited_version", ""))[:200]
            lines.append(f"### Edit {i}")
            lines.append("")
            lines.append(f"- **Original:** {original}")
            lines.append(f"- **Edited:** {edited}")
            lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Documents:** {n_docs}")
    lines.append(f"- **Total Suggestions:** {n_sugs}")
    lines.append(f"- **Total Edits:** {n_edits}")
    lines.append(f"- **Avg Sources per Suggestion:** {avg_sources:.1f}")
    lines.append("")

    return "\n".join(lines)


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
        elif format == "markdown":
            return PlainTextResponse(
                content=_format_audit_markdown(report, session.session_id),
                media_type="text/markdown",
            )
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

    review_state_path = session_path / "review_state.json"
    if review_state_path.exists():
        try:
            review_map = json.loads(review_state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            review_map = {}
        for entry in data:
            qid = entry.get("question_id")
            rs = review_map.get(qid) if qid else None
            if rs:
                entry["review_state"] = rs.get("state")
                if rs.get("state") == "dismissed":
                    entry["final_value"] = None
                elif rs.get("value") is not None:
                    entry["final_value"] = rs["value"]
                elif rs.get("selected_id") is not None:
                    entry["final_value"] = rs["selected_id"]
                elif rs.get("selected_ids") is not None:
                    entry["final_value"] = rs["selected_ids"]
                else:
                    entry["final_value"] = entry.get("answer")

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
