# Capability: Document Ingestion

Upload, parse, and prepare documents for semantic search and answer suggestion.

## MODIFIED Requirements

### Requirement: Session Document Association

The system SHALL associate uploaded documents with user sessions and remove them automatically after session expiration.

#### Scenario: Documents isolated per session

- **WHEN** documents are uploaded for a session
- **THEN** they are associated with that session ID and automatically deleted when the session expires

#### Scenario: Session expiration triggers cleanup

- **WHEN** a session's TTL is exceeded
- **THEN** a background cleanup job removes all documents associated with that session within the TTL window

#### Scenario: Client notified of remaining time

- **WHEN** a client requests session details
- **THEN** the response includes the session's remaining TTL in seconds for transparency

## Notes

- MVP scope: TTL-based automatic cleanup; manual deletion also supported
- Cleanup job runs periodically (configurable interval, default 60 minutes)
- Session TTL configurable per instance (default 48 hours)
- Failed cleanups logged; do not block other sessions
