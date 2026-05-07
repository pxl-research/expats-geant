"""Cue API: server-side review state persistence."""

import asyncio
import json
import logging
import os
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Request

from cue_api.models import ReviewStateResponse, ReviewStateUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_REVIEW_LOCKS = 1000
_review_locks: OrderedDict[str, threading.Lock] = OrderedDict()
_review_locks_lock = threading.Lock()


def _get_review_lock(session_path: Path) -> threading.Lock:
    key = session_path.name
    with _review_locks_lock:
        if key in _review_locks:
            _review_locks.move_to_end(key)
            return _review_locks[key]
        lock = threading.Lock()
        _review_locks[key] = lock
        if len(_review_locks) > _MAX_REVIEW_LOCKS:
            for old_key in list(_review_locks):
                if old_key == key:
                    continue
                if not _review_locks[old_key].locked():
                    del _review_locks[old_key]
                    break
        return lock


def _review_state_path(session_path: Path) -> Path:
    return session_path / "review_state.json"


def _read_review_state(session_path: Path) -> dict:
    path = _review_state_path(session_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_review_state(session_path: Path, state_map: dict) -> None:
    path = _review_state_path(session_path)
    fd, tmp = tempfile.mkstemp(dir=session_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state_map, f, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@router.put("/review-state/{question_id}")
async def save_review_state(question_id: str, body: ReviewStateUpdate, request: Request):
    session = request.state.session
    session_path = request.state.session_manager._get_session_path(session.session_id)

    def _save():
        with _get_review_lock(session_path):
            state_map = _read_review_state(session_path)
            state_map[question_id] = body.model_dump(exclude_none=True)
            _write_review_state(session_path, state_map)

    await asyncio.to_thread(_save)
    return {"status": "ok"}


@router.get("/review-state", response_model=ReviewStateResponse)
async def get_review_state(request: Request):
    session = request.state.session
    session_path = request.state.session_manager._get_session_path(session.session_id)

    state_map = await asyncio.to_thread(_read_review_state, session_path)
    return ReviewStateResponse(states=state_map)


@router.get("/cached-suggestions")
async def get_cached_suggestions(request: Request):
    session = request.state.session
    session_path = request.state.session_manager._get_session_path(session.session_id)
    cache_path = session_path / "cached_suggestions.json"
    if not cache_path.exists():
        return {"suggestions": {}}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    return {"suggestions": data}
