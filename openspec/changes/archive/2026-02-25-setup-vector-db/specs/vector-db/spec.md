# Capability: Vector DB (ChromaDB)

ChromaDB wrapper providing session-based document storage, semantic search, and automatic cleanup.

## ADDED Requirements

### Requirement: Session-Based Document Storage

The system SHALL maintain separate ChromaDB collections per user session for data isolation and privacy.

#### Scenario: Create session collection

- **WHEN** a session is created
- **THEN** a new ephemeral ChromaDB collection is created for that session with no initial documents

#### Scenario: Add documents to session

- **WHEN** document chunks are added for a session
- **THEN** chunks are stored in the session's collection with embeddings and metadata (source, position, timestamp)

#### Scenario: Cleanup on session end

- **WHEN** a session expires or is explicitly deleted
- **THEN** the session's ChromaDB collection is removed and all data permanently deleted

### Requirement: Semantic Search

The system SHALL perform semantic search on stored documents within a session.

#### Scenario: Search with top-k results

- **WHEN** a search query is issued for a session
- **THEN** the system returns top-k most similar chunks ranked by cosine similarity (default k=5)

#### Scenario: Metadata filtering in search

- **WHEN** search includes metadata filters (e.g., by source_filename, timestamp range)
- **THEN** results are filtered by those metadata constraints before ranking

#### Scenario: Query embedding generated

- **WHEN** a search query is issued
- **THEN** the query is embedded using the same model as documents and results are ranked by similarity

### Requirement: Embedding Generation

The system SHALL automatically generate embeddings for stored chunks using ChromaDB's built-in embedding function.

#### Scenario: Embedding created on document add

- **WHEN** a chunk is added to a session collection
- **THEN** an embedding is automatically generated via ChromaDB's default embedding function and stored with the chunk

#### Scenario: Consistent embedding model

- **WHEN** multiple queries are issued in a session
- **THEN** all embeddings (documents and queries) use the same embedding model provided by ChromaDB

### Requirement: Session Isolation

The system SHALL enforce strict isolation between concurrent user sessions.

#### Scenario: Sessions have separate collections

- **WHEN** documents are added to session A
- **THEN** session B cannot access or retrieve those documents

#### Scenario: Concurrent sessions coexist

- **WHEN** multiple sessions add documents simultaneously
- **THEN** each session's data remains isolated with no interference or data leakage

## Notes

- MVP scope: ChromaDB only (SQLite backend, ephemeral per-session) with built-in embeddings
- Each session gets a unique collection identified by session_id
- Embeddings generated automatically by ChromaDB (no external API calls)
- Located in `m_shared/vectordb/client.py`
- Dependencies: Phase 1 (Session model), Phase 2.1 (document processor)
- Future: Support for custom embedding models via OpenRouter after MVP
