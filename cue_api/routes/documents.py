"""Cue API: document upload routes."""

import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from cue_api.ingest import ingest_files_into_store, ingest_text_into_store
from cue_api.models import UploadResponse, UploadTextRequest
from cue_api.validation import FileValidationError, validate_file_upload
from m_shared.rate_limit import limiter
from m_shared.vectordb.utils import sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a document to the session for answer suggestions."""
    session = request.state.session
    manager = request.state.session_manager
    claims = request.state.claims
    max_file_size_mb = request.app.state.max_file_size_mb
    audit_logger = request.app.state.audit_logger
    llm_client = getattr(request.state, "llm_client", None) or request.app.state.llm_client

    temp_dir = manager._get_session_path(session.session_id, user_id=session.user_id) / "uploads"
    temp_dir.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name if file.filename else "upload"
    file_path = temp_dir / safe_name
    if not file_path.resolve().is_relative_to(temp_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    try:
        # Stream to disk with size enforcement
        max_bytes = max_file_size_mb * 1024 * 1024
        bytes_written = 0
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise FileValidationError(f"File too large (max {max_file_size_mb} MB)")
                f.write(chunk)

        is_valid, error_msg = validate_file_upload(str(file_path), max_size_bytes=max_bytes)
        if not is_valid:
            raise FileValidationError(error_msg)

        _image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        if Path(file_path).suffix.lower() in _image_extensions and llm_client is None:
            raise FileValidationError(
                "Image uploads are not supported: no LLM client is configured"
            )

        try:
            store = manager.get_vector_store(session.session_id)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
            )

        await asyncio.to_thread(
            ingest_files_into_store,
            file_paths=[str(file_path)],
            store=store,
            session_id=session.session_id,
            user_id=claims.get("user_id"),
            audit_logger=audit_logger,
            llm_client=llm_client,
            model_name=getattr(llm_client, "model_name", None),
        )

        file_size = os.path.getsize(file_path)
        upload_timestamp = datetime.now(UTC).isoformat()

        return UploadResponse(
            status="success",
            filename=file.filename or "unknown",
            size_bytes=file_size,
            upload_timestamp=upload_timestamp,
            session_id=session.session_id,
        )

    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"File validation failed: {e}"
        )
    except Exception as e:
        logger.error("Upload failed for session %s: %s", session.session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed"
        )
    finally:
        file_path.unlink(missing_ok=True)


@router.post("/upload-text", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_text(request: Request, body: UploadTextRequest):
    """Ingest a plain-text snippet into the session RAG store."""
    max_file_size_mb = request.app.state.max_file_size_mb
    audit_logger = request.app.state.audit_logger

    if not body.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="text must not be empty"
        )
    max_text_bytes = max_file_size_mb * 1024 * 1024
    if len(body.text.encode()) > max_text_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"text exceeds maximum allowed size of {max_file_size_mb} MB",
        )

    session = request.state.session
    claims = request.state.claims
    manager = request.state.session_manager

    try:
        store = manager.get_vector_store(session.session_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
        )

    label = (body.label or "").strip() or "pasted text"
    if not sanitize_filename(label):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label contains no usable characters after sanitization",
        )
    await asyncio.to_thread(
        ingest_text_into_store,
        text=body.text,
        label=label,
        store=store,
        session_id=session.session_id,
        user_id=claims.get("user_id"),
        audit_logger=audit_logger,
    )

    return UploadResponse(
        status="success",
        filename=label,
        size_bytes=len(body.text.encode()),
        upload_timestamp=datetime.now(UTC).isoformat(),
        session_id=session.session_id,
    )
