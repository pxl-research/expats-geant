## ADDED Requirements

### Requirement: Mid-Review Document Upload

The survey review page SHALL provide an in-page upload widget that lets respondents
add one or more documents or a text snippet without leaving the page. Uploads SHALL
be forwarded to the existing Cue document ingestion API via the UI proxy routes
already in place (`/session/{id}/upload-doc` and
`/session/{id}/upload-text-snippet`). On success, the UI SHALL refresh its view of
session state (document list and `last_upload_at`) without discarding the
respondent's in-progress form input, cached suggestions, or review state.

#### Scenario: Document uploaded from review page

- **WHEN** a respondent uploads a document via the in-page widget on the review page
- **THEN** the file is posted to the Cue ingestion API
- **AND** on success the document list on the review page updates
- **AND** the respondent's current form values, accepted/dismissed states, and
  cached suggestions are preserved

#### Scenario: Text snippet uploaded from review page

- **WHEN** a respondent submits a text snippet via the in-page widget on the review
  page
- **THEN** the text is posted to `/session/{id}/upload-text-snippet`
- **AND** the same preservation guarantees apply as for file uploads

#### Scenario: Upload failure shown inline

- **WHEN** the ingestion API returns an error for a mid-review upload
- **THEN** an inline error message is displayed next to the upload widget
- **AND** the page state is otherwise unchanged

### Requirement: Per-Question Suggestion Regenerate Button

Each suggestion block SHALL render a **Regenerate** button when the cached suggestion's
`generated_at` is earlier than the session's `last_upload_at`. When `last_upload_at`
is absent (no documents) or the cached suggestion has no `generated_at`, the button
SHALL NOT be shown. Clicking the button SHALL request a fresh suggestion for that
single question via the regenerate stream proxy and SHALL disable itself until the
matching new suggestion arrives.

#### Scenario: Button visible after new upload

- **WHEN** a new document has been ingested after a cached suggestion was generated
- **THEN** the Regenerate button is visible inside that question's suggestion block

#### Scenario: Button hidden when up-to-date

- **WHEN** the cached suggestion's `generated_at` is greater than or equal to the
  session's `last_upload_at`
- **THEN** the Regenerate button is not rendered for that question

#### Scenario: Click triggers single-question regenerate

- **WHEN** the respondent clicks Regenerate on a question
- **THEN** the UI opens an SSE connection to the regenerate-stream proxy scoped to
  that question's id
- **AND** the button is disabled while the request is in flight

#### Scenario: Button hides after new suggestion arrives

- **WHEN** the regenerated suggestion is received and rendered into the block
- **THEN** the new cached `generated_at` is at least `last_upload_at`
- **AND** the Regenerate button is no longer rendered

#### Scenario: Button reappears on further upload

- **WHEN** another document is uploaded after a question has been regenerated
- **THEN** the Regenerate button reappears on that question

### Requirement: Bulk Regenerate Untouched Suggestions

The review page SHALL provide a **Regenerate untouched suggestions** action,
positioned alongside "Accept all suggestions". The action SHALL be enabled iff at
least one question in the survey satisfies *both*:

1. No entry exists for the question in server-side review state (the question is
   neither accepted nor dismissed nor explicitly edited).
2. The cached suggestion's `generated_at` is earlier than the session's
   `last_upload_at`.

Triggering the action SHALL display a confirmation dialog stating how many
questions will be regenerated and noting that the operation may take a while. On
confirmation, the UI SHALL open an SSE connection to the regenerate-stream proxy
with the matching question ids. The action SHALL remain disabled until the stream
closes (via `event: done`, `event: error`, or transport termination), preventing
overlapping regeneration streams.

#### Scenario: Action disabled when no candidates exist

- **WHEN** every question either has a review state set or its cached suggestion
  is at least as recent as `last_upload_at`
- **THEN** the bulk action is disabled (and visually marked as such)

#### Scenario: Confirm dialog states the count

- **WHEN** the respondent triggers the bulk action
- **THEN** a confirmation dialog appears stating the number of questions that will
  be regenerated
- **AND** the dialog uses user-friendly wording ("This may take a while") without
  referencing implementation details

#### Scenario: Action regenerates only matching questions

- **WHEN** the respondent confirms the bulk action
- **THEN** the regenerate stream is opened with exactly the ids that satisfied the
  untouched-and-stale predicate at click time
- **AND** questions with an existing review state (accepted/dismissed/edited) are
  not included

#### Scenario: Action disabled during stream

- **WHEN** the bulk regenerate stream is in flight
- **THEN** the action button is disabled
- **AND** clicking it has no effect until the stream completes or fails

#### Scenario: Action re-enables after stream ends

- **WHEN** the regenerate stream emits `event: done`, emits `event: error`, or the
  transport closes
- **THEN** the bulk action button returns to its computed enabled/disabled state
  based on the latest cache and `last_upload_at`

### Requirement: Regenerate Stream Proxy

The UI SHALL expose `GET /session/{id}/regenerate-stream` as a sibling of
`/suggest-stream`. The route SHALL forward to `POST /suggest/stream` on the Cue API
**without** filtering against the per-session cached suggestions, so that questions
whose cached entry already exists are re-generated. The route SHALL accept an
optional `ids` query parameter listing the question ids to regenerate; when present,
only those ids are sent upstream. When the parameter is absent, the route SHALL send
the full set of survey items eligible for suggestion (all non-descriptive
questions).

#### Scenario: Regenerate stream bypasses cache filter

- **WHEN** the UI opens `/session/{id}/regenerate-stream?ids=q1,q2`
- **THEN** the upstream `POST /suggest/stream` request includes `q1` and `q2` as
  items
- **AND** the proxy does not remove them on the basis of existing cached entries

#### Scenario: Regenerate stream emits standard suggestion events

- **WHEN** the upstream emits `event: suggestion` for a regenerated item
- **THEN** the proxy re-renders the suggestion block HTML using the same partial as
  the initial stream
- **AND** clients can reuse their existing SSE handlers without modification
