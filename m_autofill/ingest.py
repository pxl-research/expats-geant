"""Core ingestion logic for M-Autofill (no UI).

Adapted from `demo_code/demos/rag/launch_upload_ui.py`.

Takes a list of file paths, converts to markdown, chunks, builds basic metadata,
then stores chunks in Chroma.
"""

from __future__ import annotations

from typing import Iterable

from tqdm import tqdm

from m_shared.vectordb import (
    ChromaDocumentStore,
    document_to_markdown,
    iterative_chunking,
    sanitize_filename,
)


def ingest_files_into_store(
    *,
    file_paths: Iterable[str],
    store: ChromaDocumentStore,
    max_chunk_size: int = 1024,
) -> list[str]:
    """Ingest documents into a Chroma-backed store.

    Args:
        file_paths: Paths to documents (pdf/docx/pptx/xlsx/etc.)
        store: ChromaDocumentStore instance
        max_chunk_size: Chunk size in characters

    Returns:
        List of document (collection) names added
    """

    added: list[str] = []

    current_documents = set(store.list_documents())

    for file_path in file_paths:
        collection_name = sanitize_filename(file_path)
        if collection_name in current_documents:
            continue

        md_text = document_to_markdown(file_path)
        chunks = iterative_chunking(md_text, max_size=max_chunk_size)
        meta_info = [
            {
                "source": file_path,
                "id": f"chunk_{i}",
                "chunk_index": i,
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

    return added
