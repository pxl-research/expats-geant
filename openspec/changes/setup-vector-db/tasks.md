# Phase 2.2: Vector Database (ChromaDB) Implementation Tasks

## 1. Setup & Dependencies

- [ ] 1.1 Add chromadb to `requirements.txt` (latest stable version)
- [ ] 1.2 Create `m_shared/vectordb/` directory with `__init__.py`
- [ ] 1.3 Create `m_shared/vectordb/client.py` module skeleton

## 2. Session Collection Management

- [ ] 2.1 Implement `VectorDBClient` class with ChromaDB backend
- [ ] 2.2 Implement `create_session_collection(session_id: str) -> Collection` method
- [ ] 2.3 Implement `get_session_collection(session_id: str) -> Collection` method
- [ ] 2.4 Implement `delete_session_collection(session_id: str) -> bool` method
- [ ] 2.5 Store session metadata (creation time, last accessed time) for TTL tracking
- [ ] 2.6 Unit tests for collection lifecycle (create, get, delete)

## 3. Document Storage

- [ ] 3.1 Implement `add_documents(session_id: str, chunks: list[dict]) -> bool`
  - `chunks` should include text, metadata (source, position, timestamp)
- [ ] 3.2 Validate chunk structure before storage
- [ ] 3.3 Unit tests for document addition and metadata preservation

## 4. Embedding Generation

- [ ] 4.1 Integrate with Phase 1 LLM client for embedding generation
- [ ] 4.2 Implement `_generate_embedding(text: str) -> list[float]` using OpenRouter
- [ ] 4.3 Cache embedding model selection (use consistent model across session)
- [ ] 4.4 Unit tests for embedding generation (mock LLM responses)

## 5. Semantic Search

- [ ] 5.1 Implement `search(session_id: str, query: str, top_k: int = 5) -> list[dict]` method
- [ ] 5.2 Generate embedding for query using same model as documents
- [ ] 5.3 Return results ranked by cosine similarity with metadata intact
- [ ] 5.4 Unit tests for search accuracy (verify relevance ranking)

## 6. Metadata Filtering

- [ ] 6.1 Implement `search_with_filter(session_id: str, query: str, filters: dict, top_k: int = 5) -> list[dict]`
  - Support filtering by source_filename, source_id, timestamp ranges
- [ ] 6.2 Unit tests for filtered search (verify filtering accuracy)

## 7. Session Isolation Verification

- [ ] 7.1 Unit tests confirming separate collections per session
- [ ] 7.2 Unit tests verifying no data leakage between sessions
- [ ] 7.3 Unit tests for concurrent session handling

## 8. Configuration

- [ ] 8.1 Add environment variables: CHROMADB_PATH, EMBEDDING_MODEL
- [ ] 8.2 Update `.env.example` with new variables
- [ ] 8.3 Add config validation at client initialization

## 9. Testing

- [ ] 9.1 Unit tests for all VectorDBClient methods
- [ ] 9.2 Integration test: document processor output → add_documents → search
- [ ] 9.3 All tests passing, 80%+ code coverage

## 10. Documentation

- [ ] 10.1 Docstrings for all public methods
- [ ] 10.2 Brief README in `m_shared/vectordb/` explaining client usage
