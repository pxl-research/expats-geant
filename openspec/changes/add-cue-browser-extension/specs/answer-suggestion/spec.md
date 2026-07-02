## ADDED Requirements

### Requirement: LLM-Assisted Form Extraction Endpoint

The system SHALL provide a `POST /extract-form` endpoint that accepts the text
content and URL of a web page and returns a list of `BatchSuggestItem` entries
in the same shape consumed by `POST /suggest/batch` and `POST /suggest/stream`.
The endpoint SHALL be session-authenticated using the existing JWT contract
and SHALL be invoked only as a third-tier fallback by clients (e.g. the
browser extension) when deterministic extractors return zero items.

The endpoint SHALL use the configured LLM to produce items in the form
`{id, type, prompt, choices?: [{id, label}]}` where `type` is one of
`open_ended`, `single_choice`, `multiple_choice`, or `slider`. The `id` field
SHALL be a synthetic identifier the client can map back to a DOM element.

The endpoint SHALL record an audit event of type `EXTRACT_FORM` per
`audit-compliance` capability conventions, capturing the source URL, the
number of items extracted, and the LLM model used.

#### Scenario: Page text returns structured items

- **WHEN** an authenticated client posts the text content and URL of a page
  containing a form to `POST /extract-form`
- **THEN** the endpoint returns a JSON array of `BatchSuggestItem` entries
- **AND** each entry has a `type` of `open_ended`, `single_choice`,
  `multiple_choice`, or `slider`

#### Scenario: Choice questions include choice labels

- **WHEN** the LLM identifies a choice-type question in the page text
- **THEN** the returned item includes a `choices` array with `{id, label}`
  pairs

#### Scenario: Audit event recorded

- **WHEN** the endpoint returns successfully
- **THEN** an audit event of type `EXTRACT_FORM` is recorded against the
  caller's session
- **AND** the event includes the source URL, item count, and LLM model

#### Scenario: Unauthenticated request rejected

- **WHEN** the request lacks a valid session JWT
- **THEN** the endpoint returns HTTP 401 Unauthorized
- **AND** no LLM call is made

#### Scenario: Empty or unparseable page text

- **WHEN** the LLM cannot identify any form fields in the supplied text
- **THEN** the endpoint returns an empty JSON array
- **AND** an audit event is still recorded with `item_count: 0`

#### Scenario: LLM error surfaced gracefully

- **WHEN** the LLM call fails (timeout, parse error, provider outage)
- **THEN** the endpoint returns HTTP 502 Bad Gateway with a stable error code
- **AND** no partial or malformed item list is returned
