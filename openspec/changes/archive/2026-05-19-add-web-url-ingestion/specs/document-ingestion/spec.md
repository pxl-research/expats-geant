## ADDED Requirements

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
