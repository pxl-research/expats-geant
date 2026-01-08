# Capability: Vector DB (ChromaDB)

ChromaDB wrapper providing session-based document storage, semantic search, and automatic TTL-based cleanup.

## ADDED Requirements

### Requirement: Session-Based Document Storage

The system SHALL maintain separate ChromaDB instances per user session for data isolation.

#### Scenario: Create session collection

- **WHEN** a session is created
- **THEN** a new ephemeral ChromaDB collection is created for that session

#### Scenario: Add documents to session

- **WHEN** document chunks are uploaded for a session
- **THEN** chunks are stored in the session's collection with metadata (source, position, timestamp)

#### Scenario: Cleanup on session end

- **WHEN** a session expires or is explicitly deleted
- **THEN** the session's ChromaDB collection is removed and all data deleted

### Requirement: Semantic Search

The system SHALL perform semantic search on stored documents within a session.

#### Scenario: Search with top-k results

- **WHEN** a search query is issued
- **THEN** the system returns top-k most similar chunks ranked by cosine similarity

#### Scenario: Metadata filtering in search

- **WHEN** search includes metadata filters (e.g., by source_id)
- **THEN** results are filtered by those metadata constraints

### Requirement: Document Chunking

The system SHALL split documents into manageable chunks with metadata preservation.

#### Scenario: Text document chunking

- **WHEN** a text document is chunked
- **THEN** chunks preserve source, position (byte offset or line number), and timestamp

#### Scenario: Configurable chunk size

- **WHEN** chunk strategy is configured
- **THEN** documents are split respecting chunk size and sentence boundaries

### Requirement: TTL-Based Cleanup

The system SHALL automatically remove expired session data.

#### Scenario: Cleanup task removes expired sessions

- **WHEN** a background cleanup job runs
- **THEN** all sessions past their TTL are identified and their data deleted

### Requirement: Embedding Generation

The system SHALL generate embeddings for stored chunks (via OpenRouter or default provider).

#### Scenario: Embedding created on document add

- **WHEN** a chunk is added to ChromaDB
- **THEN** an embedding is generated and stored with the chunk

## Notes

- MVP scope: ChromaDB only (SQLite backend, no persistent cloud store)
- Session isolation: Each session gets its own in-memory or temp-file collection
- Required env vars: CHROMADB_PATH, SESSION_TTL_HOURS
- Located in `m_shared/vectordb/client.py`
