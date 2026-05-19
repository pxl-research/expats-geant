## ADDED Requirements

### Requirement: Web URL Source Panel

When web ingestion is enabled at the deployment level, the survey UI SHALL render
an **Add web source** panel on both the documents upload page and the mid-review
upload widget. The panel SHALL contain a URL input, a **Preview** action that
calls the preview endpoint and renders the result in place, and an inline
preview area showing the extracted title, final URL, content type, character
count, the first 500 characters of extracted text, and any warnings returned by
the server. From the preview view, the user SHALL be able to commit the source
via **Add as source** or discard it via **Discard**. Only **Add as source**
SHALL trigger the ingest endpoint.

When web ingestion is disabled at the deployment level, the panel SHALL NOT be
rendered at all; the page SHALL look as it does today.

#### Scenario: Panel hidden when operator flag is off

- **WHEN** the Cue API reports that web ingestion is disabled
- **THEN** neither the documents page nor the mid-review widget renders the
  Add web source panel

#### Scenario: Preview rendered inline

- **WHEN** the user submits a URL via the panel
- **THEN** the UI fetches the preview from the API and replaces the panel
  body with the preview partial (title, final URL, content-type pill,
  500-character preview, warnings, **Add as source** / **Discard** buttons)
- **AND** no chunks are written to the session vector store at this stage

#### Scenario: Add as source commits the ingest

- **WHEN** the user clicks **Add as source** in the preview view
- **THEN** the UI calls the ingest endpoint for the URL
- **AND** on success, the document list updates to include the new web source
- **AND** the panel resets to accept a new URL

#### Scenario: Discard clears the preview without ingesting

- **WHEN** the user clicks **Discard** in the preview view
- **THEN** the preview is cleared and the panel returns to its empty URL-input
  state
- **AND** no ingest request is made

### Requirement: Per-Session Web Source Consent Toggle

When web ingestion is enabled at the deployment level, the UI SHALL render a
**Allow web sources** toggle alongside the Add web source panel. The toggle
SHALL default to off, persist via the per-session consent endpoint, and gate
the panel's interactivity: while the toggle is off, the URL input and Preview
action SHALL be disabled and a one-line explanation SHALL be visible
("URLs are fetched by the server and recorded in your audit report.").

#### Scenario: Toggle defaults to off

- **WHEN** the documents or review page loads for a new session
- **THEN** the **Allow web sources** toggle is rendered in the off position
- **AND** the URL input is disabled

#### Scenario: Toggle on enables the panel

- **WHEN** the user toggles **Allow web sources** to on
- **THEN** the UI calls the consent endpoint to persist the choice
- **AND** the URL input becomes interactive

#### Scenario: Toggle off after granting consent

- **WHEN** the user toggles **Allow web sources** off after previously
  granting consent
- **THEN** the UI calls the consent endpoint to revoke the flag
- **AND** the URL input is disabled
- **AND** previously ingested web sources remain in the session and continue
  to inform suggestions

### Requirement: Web Source Preview Warnings and Errors

The preview view SHALL surface server-returned warnings (notably
`likely_js_rendered`) as inline messages with concrete next-step advice, and
SHALL render server-returned errors in a clearly differentiated error block.
Errors SHALL NOT close the preview view automatically — the user can re-enter
the URL or paste a different one.

#### Scenario: JavaScript-rendered page warning shown

- **WHEN** the preview response includes a `likely_js_rendered` warning
- **THEN** the preview view shows an inline warning recommending that the
  user save the page as a PDF and upload it instead
- **AND** the **Add as source** button remains enabled (the user can choose
  to ingest the sparse content anyway)

#### Scenario: Network or HTTP error rendered inline

- **WHEN** the preview request fails (timeout, network error, HTTP 4xx/5xx
  from the origin)
- **THEN** the UI renders an inline error block describing the failure
- **AND** the URL input retains its value so the user can correct it or
  retry

#### Scenario: Unsupported media type error

- **WHEN** the API returns HTTP 415 for an unsupported content type
- **THEN** the UI renders a clear message stating which type was returned
  and which types are accepted
- **AND** suggests downloading and uploading the file directly

### Requirement: Re-Ingest Confirmation UX

The preview view SHALL display a prior-ingest notice when the preview response
includes a non-null `already_ingested_at` timestamp. The notice SHALL be of the
form "You ingested this URL on [date]. Confirming will replace the previous
version." The user SHALL still be able to confirm via **Add as source** or
back out via **Discard**.

#### Scenario: Prior-ingest message shown

- **WHEN** the preview response includes a non-null `already_ingested_at`
  field
- **THEN** the preview view displays a clearly visible notice stating the
  prior ingest date and that confirming will replace the previous version

#### Scenario: Confirm triggers overwrite

- **WHEN** the user clicks **Add as source** on a re-ingest preview
- **THEN** the ingest endpoint is called as for a first-time ingest
- **AND** the document list reflects one entry for the URL after success
