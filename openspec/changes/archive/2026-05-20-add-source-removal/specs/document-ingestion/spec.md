## ADDED Requirements

### Requirement: Session Source Removal

The system SHALL support removing an individual ingested source from a
session's vector store via an authenticated endpoint. `DELETE
/session/documents/{name}` SHALL resolve the path parameter through the
same sanitisation used at ingest time, locate the matching collection,
and delete the entire collection (all chunks for the named source). On
success the endpoint SHALL emit a `SOURCE_REMOVED` audit event and
return HTTP 200 with `{"status": "ok", "name": <name>}`. When no
collection matches the requested name, the endpoint SHALL return HTTP
404 with a clear message. The operation SHALL be idempotent: a second
DELETE for the same name simply returns 404 without side effects.

The endpoint SHALL respect session isolation: a DELETE authenticated for
session A SHALL NOT affect sources in session B.

#### Scenario: Remove an ingested source

- **WHEN** `DELETE /session/documents/{name}` is called with a JWT for
  a session that contains a source by that name
- **THEN** the collection is deleted from the session's vector store
- **AND** the response is HTTP 200 with `{"status": "ok", "name": <name>}`
- **AND** subsequent calls to `GET /session/stats` no longer list the
  source

#### Scenario: Unknown source name returns 404

- **WHEN** `DELETE /session/documents/{name}` is called with a name
  that does not match any collection in the session
- **THEN** the response is HTTP 404 with a message indicating the
  source was not found
- **AND** no audit event is emitted

#### Scenario: Cross-session isolation

- **WHEN** session A and session B each contain a source named "doc.pdf"
- **AND** `DELETE /session/documents/doc.pdf` is called for session A
- **THEN** only session A's "doc.pdf" is removed
- **AND** session B's "doc.pdf" remains intact

### Requirement: Source Removal Audit Event

The system SHALL record every successful source removal as a
`SOURCE_REMOVED` audit event. The event SHALL include the source name,
`source_kind` (file/web/text/null), and `source_mime` (the MIME type or
null) as captured from the source's chunk metadata at the moment of
deletion. The `SOURCE_REMOVED` event type SHALL be exposed in the audit
report alongside `UPLOAD`, `WEB_FETCH`, and other existing event types.

The audit log SHALL retain both the original ingest event and the
later `SOURCE_REMOVED` event so that the lifecycle of a source within
a session is reconstructable.

#### Scenario: Removal emits an audit event with provenance

- **WHEN** a source with `source_kind = "web"` and
  `source_mime = "text/html"` is successfully removed
- **THEN** a `SOURCE_REMOVED` audit event is logged with the source
  name, `source_kind = "web"`, and `source_mime = "text/html"`

#### Scenario: Legacy source removal logs null provenance fields

- **WHEN** a source ingested before kind/mime tracking was added is
  removed
- **THEN** the `SOURCE_REMOVED` audit event still records the source
  name but with `source_kind = null` and `source_mime = null`

#### Scenario: Audit history preserved across ingest and removal

- **WHEN** a source is ingested and later removed in the same session
- **THEN** the audit log retains both the original `UPLOAD` (or
  `WEB_FETCH` with `ingested=true`) event and the subsequent
  `SOURCE_REMOVED` event

### Requirement: Source Removal Leaves Cached Suggestions Untouched

The source removal operation SHALL NOT modify or invalidate any cached
suggestions. Suggestions that were generated against an evidence set
containing the now-removed source SHALL retain their citation footers
as-is. Users who want suggestions refreshed against the trimmed source
set SHALL use the existing per-question Regenerate action or the bulk
"Regenerate untouched" action.

This decision preserves user review state (edits, dismissals, accepts)
and keeps citation footers truthful about the evidence available at
generation time. The audit log makes the source-removal action
discoverable for any later reconciliation.

#### Scenario: Cached suggestion citing a removed source is not modified

- **WHEN** a session contains a cached suggestion whose citations
  reference source S
- **AND** source S is removed via `DELETE /session/documents/S`
- **THEN** the cached suggestion's text and citations remain unchanged
- **AND** no automatic regeneration is triggered

#### Scenario: Manual regeneration excludes the removed source

- **WHEN** a user clicks the per-question Regenerate button after
  source S has been removed
- **THEN** the new suggestion is computed against the remaining sources
  only
- **AND** the cached suggestion entry is overwritten by the new result
