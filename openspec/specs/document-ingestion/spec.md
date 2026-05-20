# Capability: Document Ingestion

## Purpose

Upload, parse, and prepare documents for semantic search and answer suggestion.
## Requirements
### Requirement: Multi-Format Document Upload

The system SHALL accept documents in common formats for Cue sessions. Supported formats
are: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, and images
(`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`).

#### Scenario: Upload text file

- **WHEN** a `.txt` or `.md` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload PDF document

- **WHEN** a `.pdf` file is uploaded
- **THEN** the file is stored and queued for text extraction via PDF parser

#### Scenario: Upload Word document

- **WHEN** a `.docx` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload Office document

- **WHEN** a `.pptx`, `.xlsx`, or `.xls` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload image file

- **WHEN** a `.jpg`, `.jpeg`, `.png`, `.gif`, or `.webp` file is uploaded
- **THEN** the file is queued for LLM-based image-to-text conversion before ingestion

#### Scenario: Reject unsupported format

- **WHEN** a file with an unsupported extension is uploaded
- **THEN** the request is rejected with HTTP 400 and a list of allowed extensions is returned

### Requirement: Text Extraction

The system SHALL extract readable text from uploaded documents.

#### Scenario: Extract text from PDF

- **WHEN** PDF text extraction completes
- **THEN** text is returned with position metadata (page number, approximate position)

#### Scenario: Extract text from Word doc

- **WHEN** Word document extraction completes
- **THEN** text is returned with position metadata (paragraph number, section)

### Requirement: Document Chunking

The system SHALL split extracted text into chunks suitable for embedding.

#### Scenario: Chunk text by sentence boundaries

- **WHEN** text is chunked
- **THEN** chunks respect sentence/paragraph boundaries (not mid-word splits)

### Requirement: Metadata Tagging

The system SHALL preserve document metadata for citation accuracy.

#### Scenario: Store chunk metadata

- **WHEN** a chunk is created
- **THEN** it retains source filename, position/percentage, timestamp, and optional highlights

### Requirement: Session Document Association

The system SHALL associate uploaded documents with user sessions.

#### Scenario: Documents isolated per session

- **WHEN** documents are uploaded for a session
- **THEN** they are stored only for that session and deleted when session expires

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

### Requirement: Image-to-Text Conversion

The system SHALL convert uploaded image files to Markdown text descriptions using an LLM
before chunking and ingestion. The LLM prompt SHALL request a detailed description in
English using Markdown format. If no LLM client is configured, image files SHALL be
skipped with a warning and SHALL NOT cause an error for the overall upload request.

#### Scenario: Image ingested via LLM description

- **WHEN** an image file is uploaded and an LLM client is available
- **THEN** the image is passed to the LLM with a description prompt
- **AND** the returned Markdown text is chunked and stored in the session vector store
- **AND** chunk metadata records the original image filename as the source

#### Scenario: Image skipped without LLM client

- **WHEN** an image file is uploaded and no LLM client is configured
- **THEN** the image is skipped
- **AND** a warning is logged
- **AND** the remaining files in the upload batch continue to be processed normally

### Requirement: Web URL Ingestion

The system SHALL support ingesting content from a user-provided web URL through a
two-step preview/confirm flow. `POST /web/preview` SHALL fetch the URL, extract
content, and return a preview payload without modifying the session vector store.
`POST /web/ingest` SHALL fetch the URL (using a recent preview cache when
available), extract content, and store the resulting chunks in the session vector
store. Both endpoints SHALL emit a `WEB_FETCH` audit event recording the URL,
final URL after redirects, content type, extracted-text length, and an
`ingested` flag distinguishing preview-only fetches from committed ones.

#### Scenario: Preview returns extracted content without storing

- **WHEN** `POST /web/preview` is called with a reachable URL
- **THEN** the response includes title, final URL, content type, extracted-text
  character count, a 500-character preview text, and any warnings
- **AND** no chunks are written to the session vector store
- **AND** a `WEB_FETCH` audit event with `ingested=false` is logged

#### Scenario: Ingest stores chunks for the URL

- **WHEN** `POST /web/ingest` is called with a URL previously previewed within
  the cache TTL
- **THEN** the extracted text is chunked and stored in the session vector store
- **AND** every chunk carries `source_url` metadata equal to the final URL
- **AND** a `WEB_FETCH` audit event with `ingested=true` is logged

#### Scenario: Ingest re-fetches when preview cache has expired

- **WHEN** `POST /web/ingest` is called for a URL whose preview cache TTL has
  elapsed
- **THEN** the URL is re-fetched and re-extracted before chunks are written
- **AND** the audit event reflects the new fetch's metadata

### Requirement: Web Source Content-Type Routing

The web ingestion path SHALL inspect the response `Content-Type` header and route
extraction by media type. HTML responses (`text/html`, `application/xhtml+xml`)
SHALL be extracted using Trafilatura with precision-favouring settings and
markdown output. PDF, Office (`.docx`, `.pptx`, `.xlsx`), and plain-text /
markdown responses SHALL be routed through the existing MarkItDown path used for
file uploads. Other media types (images, archives, video, binaries) SHALL be
rejected with HTTP 415 (Unsupported Media Type) and a clear error message listing
the accepted types.

#### Scenario: HTML routed to Trafilatura

- **WHEN** a fetched URL returns `Content-Type: text/html`
- **THEN** content is extracted with Trafilatura using
  `favor_precision=True` and `output_format="markdown"`

#### Scenario: PDF URL routed to MarkItDown

- **WHEN** a fetched URL returns `Content-Type: application/pdf`
- **THEN** the response body is handed to the MarkItDown extractor used for
  file uploads
- **AND** the resulting chunks share the same metadata shape as a PDF file
  upload

#### Scenario: Unsupported media type rejected

- **WHEN** a fetched URL returns an unsupported `Content-Type` (e.g.
  `image/png`, `application/zip`)
- **THEN** the preview/ingest endpoint returns HTTP 415 with a message listing
  the accepted media types

### Requirement: Web Re-Ingest Overwrite Semantics

The system SHALL apply overwrite semantics when re-ingesting a URL that already
exists in the session: prior chunks tagged with the same `source_url` SHALL be
deleted before the freshly extracted chunks are written. The audit log SHALL
retain both the prior fetch event and the new fetch event.

This behaviour deliberately diverges from the duplicate-label skip applied to
file and text-snippet uploads, because a URL identifies a remote document whose
content may have changed; the user's intent in re-ingesting is to refresh the
snapshot.

#### Scenario: Re-ingest replaces prior chunks for the same URL

- **WHEN** `POST /web/ingest` is called for a URL that already exists as a
  source in the session
- **THEN** all chunks tagged with that `source_url` are deleted before the new
  chunks are written
- **AND** the vector store ends with exactly one set of chunks for that URL

#### Scenario: Re-ingest preserves audit history

- **WHEN** a URL is ingested more than once in a session
- **THEN** the audit log retains a `WEB_FETCH` event for each fetch with its
  own timestamp and extracted-bytes count

#### Scenario: Preview surfaces prior ingest timestamp

- **WHEN** `POST /web/preview` is called for a URL already ingested in the
  session
- **THEN** the response includes an `already_ingested_at` ISO 8601 timestamp
  indicating the most recent prior ingest

### Requirement: Operator Web Ingestion Gate

Web preview and ingestion SHALL be controlled by the `CUE_WEB_INGEST_ENABLED`
environment variable. When the variable is unset, `false`, or any value other
than a case-insensitive `true`, both `POST /web/preview` and `POST /web/ingest`
SHALL return HTTP 403 with a message indicating that web ingestion is not
enabled for the deployment.

#### Scenario: Disabled by default

- **WHEN** `CUE_WEB_INGEST_ENABLED` is unset
- **THEN** both `POST /web/preview` and `POST /web/ingest` return HTTP 403

#### Scenario: Operator enables the flag

- **WHEN** `CUE_WEB_INGEST_ENABLED=true` is configured at deployment start
- **THEN** both endpoints become available for sessions that have granted
  per-session consent

### Requirement: Per-Session Web Ingestion Consent

When the operator gate is on, each session SHALL maintain a boolean
`web_consent` flag (default `false`) persisted in session metadata. `PUT
/session/web-consent` SHALL toggle the flag. While the flag is `false`,
`POST /web/preview` and `POST /web/ingest` SHALL return HTTP 403 even if the
operator gate is on. The privacy/EULA endpoint SHALL reflect the current
value and explain the privacy implications of opting in.

#### Scenario: Default consent is off

- **WHEN** a new session is created
- **THEN** the session's `web_consent` flag is `false`

#### Scenario: Endpoints rejected without consent

- **WHEN** a session calls `POST /web/preview` or `POST /web/ingest` and its
  `web_consent` flag is `false`
- **THEN** the request returns HTTP 403 with a message asking the user to
  enable web sources first

#### Scenario: User grants consent

- **WHEN** a session calls `PUT /session/web-consent` with `{"enabled": true}`
- **THEN** subsequent `POST /web/preview` and `POST /web/ingest` calls are
  permitted (subject to the operator gate)

### Requirement: Web Fetch Hardening

The web fetch SHALL be hardened against common failure and abuse modes:

- A combined connect + read timeout of 10 seconds.
- A polite identifying `User-Agent` header naming the product and providing
  a contact URL.
- Up to 5 HTTP redirects followed; the final URL is recorded alongside the
  initial URL in the audit log.
- The response body size SHALL be capped by the existing
  `max_file_size_mb` limit used for file uploads; exceeding it returns
  HTTP 413 with a clear message.
- No automatic retries on failure; failure is surfaced to the caller.

#### Scenario: Fetch times out

- **WHEN** a URL does not respond within 10 seconds
- **THEN** the endpoint returns an error indicating the timeout and the user
  can manually retry

#### Scenario: Redirects followed and recorded

- **WHEN** a URL responds with one or more 3xx redirects (up to 5)
- **THEN** the final URL is used as the source identifier
- **AND** the audit event records both the initial URL and the final URL

#### Scenario: Oversize response rejected

- **WHEN** the fetched body exceeds `max_file_size_mb`
- **THEN** the endpoint returns HTTP 413 and no extraction is attempted

### Requirement: Likely JavaScript-Rendered Detection

The system SHALL flag a fetch with `likely_js_rendered = true` in both the
audit event and the preview response when an HTML response yields suspiciously
little extracted text relative to the response body size. The detection
threshold SHALL be: extracted text length below 200 characters on an HTML
response body larger than 5 KB.

The preview response SHALL include a user-facing warning suggesting that the
page may require browser rendering and recommending saving the page as a PDF
for ingestion.

#### Scenario: Sparse HTML extraction flagged

- **WHEN** Trafilatura extracts fewer than 200 characters from an HTML body
  larger than 5 KB
- **THEN** the preview response sets `likely_js_rendered=true`
- **AND** includes a warning recommending "save as PDF and upload" as an
  alternative

#### Scenario: Healthy HTML extraction not flagged

- **WHEN** Trafilatura extracts a substantial body of text from an HTML
  response
- **THEN** `likely_js_rendered` is `false` and no warning is added

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

## Notes

- MVP scope: Text, PDF, DOCX formats only (no audio/video transcription yet)
- Uses MarkItDown or similar library for text extraction
- Documents stored temporarily during session, deleted on cleanup
- Located in `cue_api/document_processor.py`
