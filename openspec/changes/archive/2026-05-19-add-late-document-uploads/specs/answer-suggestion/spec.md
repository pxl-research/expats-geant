## ADDED Requirements

### Requirement: Per-Item Suggestion Timestamp

The `ItemSuggestion` model SHALL include a `generated_at` field carrying the ISO 8601
timestamp at which the suggestion was produced. Both `POST /suggest/batch` and
`POST /suggest/stream` SHALL populate this field on every emitted item. The cached
suggestion store (`cached_suggestions.json`) SHALL preserve this field so that clients
reading cached entries can determine each suggestion's age independently of the batch
wrapper's `generated_at`.

#### Scenario: Batch response items carry timestamp

- **WHEN** a client calls `POST /suggest/batch` and receives a `BatchSuggestResponse`
- **THEN** each entry in `responses` includes a non-empty `generated_at` ISO 8601
  string
- **AND** the value reflects the moment the LLM call for that item completed

#### Scenario: Stream events carry timestamp

- **WHEN** a client consumes the SSE stream from `POST /suggest/stream`
- **THEN** each `event: suggestion` payload contains a `generated_at` ISO 8601 string

#### Scenario: Cache preserves timestamp

- **WHEN** a suggestion is cached for later page reloads
- **THEN** the cached entry for that item includes `generated_at`
- **AND** a subsequent `GET /cached-suggestions` returns entries with `generated_at`
  preserved

### Requirement: Suggestion Cache Upsert on Regeneration

The suggestion cache SHALL upsert entries keyed by `item_id`: when a new suggestion is
generated for an `item_id` that already has a cached entry, the cached entry is
overwritten with the new suggestion and its new `generated_at`. The append-only
answer report SHALL retain both the prior entry and the new entry, preserving the
full generation history for audit purposes.

#### Scenario: Cache entry overwritten

- **WHEN** `POST /suggest/stream` is called with an `item_id` that already has a
  cached suggestion
- **THEN** the cache entry for that `item_id` is replaced with the newly generated
  suggestion
- **AND** subsequent `GET /cached-suggestions` returns the new entry, not the old one

#### Scenario: Answer report retains both entries

- **WHEN** a suggestion is regenerated for an `item_id` that already had one entry in
  `answer_report.json`
- **THEN** the new entry is appended to the report
- **AND** the prior entry remains in the report with its original `generated_at`

### Requirement: Last Upload Timestamp in Session Stats

The `GET /session/stats` response SHALL include a `last_upload_at` field carrying the
ISO 8601 timestamp of the most recent document or text snippet ingestion in the
session. The value SHALL be `null` when no documents have been ingested.

#### Scenario: Last upload reflects most recent ingestion

- **WHEN** a session has one or more ingested documents
- **THEN** `GET /session/stats` returns `last_upload_at` equal to the ISO 8601
  representation of the most recent chunk's `ingested_at` timestamp

#### Scenario: Empty session returns null

- **WHEN** a session exists but has no ingested documents
- **THEN** `GET /session/stats` returns `last_upload_at` equal to `null`

#### Scenario: New upload advances the timestamp

- **WHEN** an additional document is ingested into an existing session
- **THEN** a subsequent `GET /session/stats` returns a `last_upload_at` value greater
  than the value returned before the upload
