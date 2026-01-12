# Capability: Vector DB (ChromaDB)

ChromaDB wrapper providing session-based document storage, semantic search, and automatic cleanup.

## MODIFIED Requirements

### Requirement: Session-Based Document Storage

The system SHALL maintain separate ChromaDB collections per user session, with automatic removal upon session expiration.

#### Scenario: Cleanup on session expiration

- **WHEN** a session's TTL expires
- **THEN** the session's ChromaDB collection is automatically removed and all data permanently deleted

#### Scenario: No residual data after cleanup

- **WHEN** a session is deleted
- **THEN** subsequent queries for that session return empty collections; no data persists

## Notes

- Cleanup cascades from session model to vector DB client
- ChromaDB collections are ephemeral by design; cleanup is definitive
- Cleanup job respects session TTL configuration for consistency
