"""Core ingestion logic for Cue (no UI).

Adapted from `demo_code/demos/rag/launch_upload_ui.py`.

Takes a list of file paths, converts to markdown, chunks, builds basic metadata,
then stores chunks in Chroma.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from m_shared.utils import AuditLogger
from m_shared.vectordb import (
    ChromaDocumentStore,
    chunk_pptx,
    document_to_markdown,
    iterative_chunking,
    sanitize_filename,
)
from m_shared.vectordb.utils import image_description

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def ingest_files_into_store(
    *,
    file_paths: Iterable[str],
    store: ChromaDocumentStore,
    max_chunk_size: int = 1024,
    session_id: str | None = None,
    user_id: str | None = None,
    audit_logger: AuditLogger | None = None,
    llm_client=None,
    model_name: str | None = None,
) -> list[str]:
    """Ingest documents into a Chroma-backed store.

    Args:
        file_paths: Paths to documents (pdf/docx/pptx/xlsx/etc.)
        store: ChromaDocumentStore instance
        max_chunk_size: Chunk size in characters
        session_id: Optional session ID for audit logging
        user_id: Optional user ID for audit logging
        audit_logger: Optional audit logger instance
        llm_client: Optional LLM client for image description
        model_name: Model name to use with llm_client for images

    Returns:
        List of document (collection) names added
    """

    added: list[str] = []

    current_documents = set(store.list_documents())

    for file_path in file_paths:
        collection_name = sanitize_filename(file_path)
        if collection_name in current_documents:
            continue

        suffix = Path(file_path).suffix.lower()
        if suffix in _IMAGE_EXTENSIONS:
            if llm_client and model_name:
                md_text = image_description(file_path, llm_client, model_name)
            else:
                logger.warning("Skipping image %s: no LLM client available", file_path)
                continue
        else:
            md_text = document_to_markdown(file_path)

        if suffix == ".pptx":
            chunks = chunk_pptx(md_text, max_size=max_chunk_size)
        else:
            chunks = iterative_chunking(md_text, max_size=max_chunk_size)
        ingested_at = datetime.utcnow().timestamp()  # Unix timestamp for ChromaDB range filtering
        total_chunks = len(chunks)
        source_mime = _EXT_TO_MIME.get(suffix, "application/octet-stream")
        meta_info = [
            {
                "source": os.path.basename(file_path),
                "id": f"chunk_{i}",
                "chunk_index": i,
                "total_chunks": total_chunks,
                "ingested_at": ingested_at,
                "source_kind": "file",
                "source_mime": source_mime,
            }
            for i in range(total_chunks)
        ]

        store.add_document(
            document_name=collection_name,
            chunks=chunks,
            meta_infos=meta_info,
            tqdm_func=tqdm,
        )

        added.append(collection_name)
        current_documents.add(collection_name)

        # Log upload to audit trail
        if audit_logger and session_id:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            file_ext = os.path.splitext(file_path)[1]

            audit_logger.log_upload(
                session_id=session_id,
                filename=os.path.basename(file_path),
                file_size=file_size,
                file_type=file_ext,
                user_id=user_id,
            )

    return added


def ingest_text_into_store(
    *,
    text: str,
    label: str,
    store: ChromaDocumentStore,
    max_chunk_size: int = 1024,
    session_id: str | None = None,
    user_id: str | None = None,
    audit_logger: AuditLogger | None = None,
) -> list[str]:
    """Ingest a plain-text snippet into a Chroma-backed store.

    Args:
        text: Raw text content to ingest
        label: Human-readable source label (used as collection name + chunk metadata)
        store: ChromaDocumentStore instance
        max_chunk_size: Chunk size in characters
        session_id: Optional session ID for audit logging
        user_id: Optional user ID for audit logging
        audit_logger: Optional audit logger instance

    Returns:
        List of collection names added (empty if label already exists)
    """
    collection_name = sanitize_filename(label)
    if not collection_name:
        raise ValueError(f"label {label!r} produces an empty collection name after sanitization")
    if collection_name in set(store.list_documents()):
        return []  # duplicate → silent skip

    chunks = iterative_chunking(text, max_size=max_chunk_size)
    ingested_at = datetime.utcnow().timestamp()
    meta_info = [
        {
            "source": label,
            "id": f"chunk_{i}",
            "chunk_index": i,
            "ingested_at": ingested_at,
            "source_kind": "text",
            "source_mime": "text/plain",
        }
        for i in range(len(chunks))
    ]

    store.add_document(
        document_name=collection_name,
        chunks=chunks,
        meta_infos=meta_info,
        tqdm_func=tqdm,
    )

    if audit_logger and session_id:
        audit_logger.log_upload(
            session_id=session_id,
            filename=label,
            file_size=len(text.encode()),
            file_type=".txt",
            user_id=user_id,
        )

    return [collection_name]


def ingest_extracted_text_into_store(
    *,
    text: str,
    source_label: str,
    source_url: str,
    content_type: str,
    store: ChromaDocumentStore,
    max_chunk_size: int = 1024,
) -> str:
    """Ingest pre-extracted text from a web URL (overwrite-by-source semantics).

    Unlike :func:`ingest_text_into_store`, this helper does NOT silently skip
    duplicates: a URL identifies a remote document whose content may have
    changed, so re-ingesting deletes the prior chunks first and writes the
    fresh ones. The caller is responsible for emitting the WEB_FETCH audit
    event (so preview-only fetches are also recorded).

    Args:
        text: Extracted text content
        source_label: Human-readable source label (used as collection name + display)
        source_url: Canonical URL after redirect resolution; stored on each chunk
        content_type: Origin Content-Type (e.g. ``"text/html"``, ``"application/pdf"``);
            stored on each chunk as ``source_mime``.
        store: ChromaDocumentStore instance
        max_chunk_size: Chunk size in characters

    Returns:
        Collection name written
    """
    collection_name = sanitize_filename(source_label)
    if not collection_name:
        raise ValueError(
            f"source_label {source_label!r} produces an empty collection name after sanitization"
        )
    if collection_name in set(store.list_documents()):
        store.remove_document(collection_name)

    chunks = iterative_chunking(text, max_size=max_chunk_size)
    ingested_at = datetime.utcnow().timestamp()
    meta_info = [
        {
            "source": source_label,
            "source_url": source_url,
            "id": f"chunk_{i}",
            "chunk_index": i,
            "ingested_at": ingested_at,
            "source_kind": "web",
            "source_mime": content_type,
        }
        for i in range(len(chunks))
    ]

    store.add_document(
        document_name=collection_name,
        chunks=chunks,
        meta_infos=meta_info,
        tqdm_func=tqdm,
    )

    return collection_name


def find_source_url_ingest_time(store: ChromaDocumentStore, source_url: str) -> float | None:
    """Return the most-recent ``ingested_at`` timestamp for the given source_url.

    Scans all collections and inspects their chunk metadata. Returns ``None``
    if the URL has never been ingested in this session. Used by
    ``POST /web/preview`` to populate the ``already_ingested_at`` field.
    """
    latest: float | None = None
    for col in store.cdb_client.list_collections():
        metadatas = col.get(include=["metadatas"]).get("metadatas") or []
        for m in metadatas:
            if (m or {}).get("source_url") != source_url:
                continue
            ts = (m or {}).get("ingested_at")
            if isinstance(ts, int | float) and (latest is None or ts > latest):
                latest = float(ts)
    return latest
