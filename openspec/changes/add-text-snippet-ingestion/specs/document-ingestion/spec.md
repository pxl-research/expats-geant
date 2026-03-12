## ADDED Requirements

### Requirement: Direct Text Snippet Ingestion

The system SHALL accept a plain-text or markdown string via `POST /upload-text` as an
alternative to file upload and ingest it into the session RAG store.

The request body SHALL contain a non-empty `text` field and an optional `label` field used
as the source identifier in chunk metadata (defaults to `"pasted text"` when omitted).

#### Scenario: Ingest valid text snippet

- **WHEN** a non-empty `text` string is submitted to `POST /upload-text`
- **THEN** the text is chunked, embedded, and stored in the session vector store
- **AND** each chunk carries `source` metadata equal to the provided or default label

#### Scenario: Reject empty text

- **WHEN** the `text` field is empty or contains only whitespace
- **THEN** a 400 Bad Request error is returned

#### Scenario: Duplicate label is skipped

- **WHEN** a snippet with the same label already exists in the session store
- **THEN** the submission is silently skipped (consistent with file deduplication behaviour)
