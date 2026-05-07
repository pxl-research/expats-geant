"""Cue API: answer suggestion routes (batch and streaming)."""

import asyncio
import json
import logging
import threading
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from cue_api.models import (
    BatchSuggestRequest,
    BatchSuggestResponse,
    CitationResult,
    ItemSuggestion,
    normalize_to_sections,
)
from m_shared.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Bounded lock pool for concurrent answer-report writes (prevents unbounded growth)
_MAX_REPORT_LOCKS = 1000
_report_locks: OrderedDict[str, threading.Lock] = OrderedDict()
_report_locks_lock = threading.Lock()


def _get_report_lock(session_path: Path) -> threading.Lock:
    key = session_path.name
    with _report_locks_lock:
        if key in _report_locks:
            _report_locks.move_to_end(key)
            return _report_locks[key]
        lock = threading.Lock()
        _report_locks[key] = lock
        # Evict oldest locks that aren't currently held
        if len(_report_locks) > _MAX_REPORT_LOCKS:
            for old_key in list(_report_locks):
                if old_key == key:
                    continue
                if not _report_locks[old_key].locked():
                    del _report_locks[old_key]
                    break
        return lock


def _append_to_answer_report(session_path: Path, entries: list[dict]) -> None:
    """Append suggestion entries to the per-session answer_report.json (JSONL format)."""
    report_path = session_path / "answer_report.json"
    with _get_report_lock(session_path):
        with open(report_path, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _build_report_entries(raw_responses: list[dict], item_prompts: dict) -> list[dict]:
    """Build answer report entries from raw RAG responses."""
    return [
        {
            "question_id": r["item_id"],
            "question": item_prompts.get(r["item_id"], ""),
            "answer": r["suggestion"],
            "reasoning": r.get("reasoning"),
            "citations": [
                {
                    "source": c.source_id,
                    "position": c.position_percentage,
                    "excerpt": c.highlights[0] if c.highlights else "",
                }
                for c in r["citations"]
            ],
            "generated_at": datetime.now(UTC).isoformat(),
        }
        for r in raw_responses
    ]


def _to_item_suggestion(r: dict) -> ItemSuggestion:
    """Convert a raw RAG response dict to an ItemSuggestion model."""
    citations = [
        CitationResult(
            source=c.source_id,
            excerpt=c.highlights[0] if c.highlights else "",
            position=c.position_percentage or 0.0,
            distance=c.metadata.get("distance") or 0.0,
            full_text=c.metadata.get("full_text") or "",
        )
        for c in r["citations"]
    ]
    return ItemSuggestion(
        item_id=r["item_id"],
        type=r["type"],
        suggestion=r["suggestion"],
        selected_id=r.get("selected_id"),
        selected_ids=r.get("selected_ids"),
        reasoning=r.get("reasoning"),
        citations=citations,
    )


@router.post("/suggest/batch", response_model=BatchSuggestResponse)
@limiter.limit("30/minute")
async def suggest_answer_batch(
    request: Request,
    batch_request: BatchSuggestRequest,
):
    """Generate answer suggestions for multiple questionnaire items."""
    rag_pipeline = request.app.state.rag_pipeline
    session_manager = request.app.state.session_manager

    if not rag_pipeline:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG pipeline not initialized (LLM client missing)",
        )

    session = request.state.session
    claims = request.state.claims
    tenant_llm_client = getattr(request.state, "llm_client", None)

    try:
        sections = normalize_to_sections(batch_request)
        raw_responses = await asyncio.to_thread(
            rag_pipeline.suggest_batch,
            sections=sections,
            session_id=session.session_id,
            assessment_id=batch_request.assessment_id,
            user_id=claims.get("user_id"),
            llm_client=tenant_llm_client,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Batch suggestion failed for session %s: %s", session.session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch suggestion failed",
        )

    responses = [_to_item_suggestion(r) for r in raw_responses]

    item_prompts = {item.id: item.prompt for section in sections for item in section.items}
    try:
        _append_to_answer_report(
            session_manager._get_session_path(session.session_id),
            _build_report_entries(raw_responses, item_prompts),
        )
    except Exception as exc:
        logger.warning("Failed to persist batch answer report: %s", exc)

    active_client = tenant_llm_client or rag_pipeline.llm_client
    return BatchSuggestResponse(
        assessment_id=batch_request.assessment_id,
        session_id=session.session_id,
        generated_at=datetime.now(UTC).isoformat(),
        model=active_client.model_name,
        responses=responses,
    )


@router.post("/suggest/stream")
@limiter.limit("30/minute")
async def suggest_answer_stream(request: Request, batch_request: BatchSuggestRequest):
    """Stream answer suggestions one-by-one via Server-Sent Events."""
    rag_pipeline = request.app.state.rag_pipeline
    session_manager = request.app.state.session_manager

    if not rag_pipeline:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG pipeline not initialized (LLM client missing)",
        )

    session = request.state.session
    claims = request.state.claims
    tenant_llm_client = getattr(request.state, "llm_client", None)
    sections = normalize_to_sections(batch_request)
    item_prompts = {item.id: item.prompt for sec in sections for item in sec.items}

    async def event_generator():
        try:
            async for r in rag_pipeline.suggest_batch_stream(
                sections,
                session.session_id,
                batch_request.assessment_id,
                user_id=claims.get("user_id"),
                llm_client=tenant_llm_client,
            ):
                item_sug = _to_item_suggestion(r)
                yield f"event: suggestion\ndata: {item_sug.model_dump_json()}\n\n"
                try:
                    await asyncio.to_thread(
                        _append_to_answer_report,
                        session_manager._get_session_path(session.session_id),
                        _build_report_entries([r], item_prompts),
                    )
                except Exception as exc:
                    logger.warning("Failed to persist stream answer report entry: %s", exc)
        except ValueError as e:
            logger.error("Stream suggest session error: %s", e)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            return
        except Exception as e:
            logger.error("Stream suggest unexpected error: %s", e)
            yield f"event: error\ndata: {json.dumps({'detail': 'Suggestion stream failed'})}\n\n"
            return

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
