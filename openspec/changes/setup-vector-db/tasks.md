# Phase 2.2: Vector Database (ChromaDB) Implementation Tasks

## 1. Setup & Dependencies

- [x] 1.1 Add chromadb to `requirements.txt` (latest stable version) — Already present: chromadb>=1.3.3
- [x] 1.2 Create `m_shared/vectordb/` directory with `__init__.py` — Already exists with comprehensive exports
- [x] 1.3 Create `m_shared/vectordb/client.py` module skeleton — Already exists with full ChromaDocumentStore implementation

## 2. Session Collection Management

- [ ] 2.1 Implement `VectorDBClient` class with ChromaDB backend — ChromaDocumentStore exists but needs refactoring for session-based architecture
- [ ] 2.2 Implement `create_session_collection(session_id: str) -> Collection` method — Partial; ChromaDocumentStore creates collections but not session-scoped
- [ ] 2.3 Implement `get_session_collection(session_id: str) -> Collection` method — Not yet implemented
- [ ] 2.4 Implement `delete_session_collection(session_id: str) -> bool` method — Exists as `remove_document()` but needs session-aware version
- [ ] 2.5 Store session metadata (creation time, last accessed time) for TTL tracking — Not yet implemented
- [ ] 2.6 Unit tests for collection lifecycle (create, get, delete) — No tests exist yet

## 3. Document Storage

- [x] 3.1 Implement `add_documents(session_id: str, chunks: list[dict]) -> bool` — ChromaDocumentStore.add_document() exists, needs session parameter
- [x] 3.2 Validate chunk structure before storage — Partially done; metadata passed through but no explicit validation
- [ ] 3.3 Unit tests for document addition and metadata preservation — No tests exist yet

## 4. Embedding Generation

- [x] 4.1 Use ChromaDB's built-in embedding function — ChromaDB handles this automatically on collection.add()
- [x] 4.2 Embedding generated on document add — Already part of ChromaDB's add() workflow
- [x] 4.3 Consistent embedding model across session — ChromaDB ensures this by design
- [x] 4.4 No additional implementation needed — ChromaDB default embedding is sufficient for MVP

## 5. Semantic Search

- [x] 5.1 Implement `search(session_id: str, query: str, top_k: int = 5) -> list[dict]` method — ChromaDocumentStore.query() exists, needs session-aware version
- [ ] 5.2 Generate embedding for query using same model as documents — Depends on 4.2
- [x] 5.3 Return results ranked by cosine similarity with metadata intact — Already implemented in repack_query_results()
- [ ] 5.4 Unit tests for search accuracy (verify relevance ranking) — No tests exist yet

## 6. Metadata Filtering

- [ ] 6.1 Implement `search_with_filter(session_id: str, query: str, filters: dict, top_k: int = 5) -> list[dict]` — Not yet implemented; ChromaDB supports where filters but not wired up
- [ ] 6.2 Unit tests for filtered search (verify filtering accuracy) — No tests exist yet

## 7. Session Isolation Verification

- [ ] 7.1 Unit tests confirming separate collections per session — No tests exist yet
- [ ] 7.2 Unit tests verifying no data leakage between sessions — No tests exist yet
- [ ] 7.3 Unit tests for concurrent session handling — No tests exist yet

## 8. Configuration

- [ ] 8.1 Add environment variables: CHROMADB_PATH (optional, defaults to in-memory for MVP)
- [ ] 8.2 Update `.env.example` with CHROMADB_PATH if needed
- [ ] 8.3 Add config validation at client initialization

## 9. Testing

- [ ] 9.1 Unit tests for all VectorDBClient methods — No tests exist yet
- [ ] 9.2 Integration test: document processor output → add_documents → search — No tests exist yet
- [ ] 9.3 All tests passing, 80%+ code coverage — No test coverage yet

## 10. Documentation

- [x] 10.1 Docstrings for all public methods — Already present in ChromaDocumentStore and utils
- [ ] 10.2 Brief README in `m_shared/vectordb/` explaining client usage — Not yet created
