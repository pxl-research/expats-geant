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
    document_to_markdown,
    iterative_chunking,
    sanitize_filename,
)
from m_shared.vectordb.utils import image_description

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


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
        chunks = iterative_chunking(md_text, max_size=max_chunk_size)
        ingested_at = datetime.utcnow().timestamp()  # Unix timestamp for ChromaDB range filtering
        meta_info = [
            {
                "source": os.path.basename(file_path),
                "id": f"chunk_{i}",
                "chunk_index": i,
                "ingested_at": ingested_at,
            }
            for i in range(len(chunks))
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
