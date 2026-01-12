# Change: Set Up Vector Database (ChromaDB) Client

## Why

M-Autofill's RAG pipeline requires semantic search capabilities to find relevant document chunks. ChromaDB provides lightweight vector storage with session-based isolation, enabling privacy-first document storage. A proper vector DB client abstraction simplifies integration with the document processor and ensures testability.

## What Changes

- Add ChromaDB client library to `requirements.txt`
- Create `m_shared/vectordb/client.py` with session-based collection management
- Implement semantic search with configurable top-k results
- Add metadata filtering in search queries
- Support automatic embedding generation via OpenRouter
- Implement collection cleanup on session termination

## Impact

- Affected specs: `specs/vector-db/spec.md`
- Affected code: New file `m_shared/vectordb/client.py`; updates to `requirements.txt` (chromadb dependency)
- Dependencies: Phase 1 (Session model) and Phase 2.1 (document processor outputs)
- Blocking: Phase 3 (RAG pipeline)
- Note: Uses ChromaDB's built-in embedding function (MVP simplicity); OpenRouter embeddings deferred to future phases

## Acceptance Criteria

- ChromaDB collections created and destroyed correctly per session
- Semantic search returns relevant results ranked by similarity
- Metadata filtering works in search queries
- Embeddings generated and stored with chunks
- Session isolation enforced (no data leakage between sessions)
- All unit tests passing
