# Change: Add Session TTL and Automatic Cleanup

## Why

Privacy by design requires automatic deletion of session data. Without TTL-based cleanup, documents and embeddings would persist indefinitely, violating data minimization principles. A background cleanup job ensures expired session data is reliably removed, protecting user privacy and managing storage.

## What Changes

- Add TTL tracking to session model (creation time, TTL duration in hours)
- Implement background cleanup job that identifies and removes expired sessions
- Expose remaining TTL in session API responses (transparency)
- Integrate cleanup with document processor and vector DB clients
- Add comprehensive integration tests for full session lifecycle

## Impact

- Affected specs: `specs/document-ingestion/spec.md`, `specs/vector-db/spec.md` (both MODIFIED to reference TTL behavior)
- Affected code:
  - `m_shared/models/session.py` (add TTL fields)
  - `m_autofill/cleanup.py` (new cleanup job module)
  - `m_autofill/document_processor.py` (update to work with TTL sessions)
  - `m_shared/vectordb/client.py` (update to work with TTL sessions)
- Dependencies: Phase 2.1 (document processor) and Phase 2.2 (vector DB)
- Blocking: Phase 3 (RAG pipeline)

## Acceptance Criteria

- Sessions track creation time and TTL correctly
- Background cleanup job removes all expired sessions reliably
- Cleanup cascades: session deletion removes documents AND vector DB collections
- API exposes remaining TTL in session responses
- Integration tests verify full lifecycle: create → add documents → expire → cleanup
- All tests passing with no data leakage after cleanup
