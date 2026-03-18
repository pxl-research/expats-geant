# survey-ui Specification

## Purpose
TBD - created by archiving change add-survey-ui. Update Purpose after archive.
## Requirements
### Requirement: API Separation

The survey UI SHALL be a standalone module (`m_ui/`) that communicates with the M-Autofill
core system exclusively via its public HTTP API. The UI SHALL NOT import Python modules from
`m_autofill/` or `m_shared/` directly.

#### Scenario: UI calls API for survey data

- **WHEN** the UI needs to render a survey
- **THEN** it calls `GET /surveys/{survey_id}` on the M-Autofill API
- **AND** does not access the internal database or model layer directly

#### Scenario: UI calls API for suggestions

- **WHEN** the UI needs to populate suggestions for a survey session
- **THEN** it calls the M-Autofill batch suggest endpoint with the survey ID and session context
- **AND** renders the returned suggestions and citations without any internal processing

### Requirement: Survey Rendering

The UI SHALL render a survey as an interactive form, deriving question layout and input controls
from the internal `Survey` model returned by the API. Question types SHALL map to appropriate
HTML input controls.

#### Scenario: Render choice question

- **WHEN** a question of type `single_choice` or `multiple_choice` is rendered
- **THEN** the UI displays labelled radio buttons or checkboxes respectively
- **AND** each answer option is shown with its text label

#### Scenario: Render open-ended question

- **WHEN** a question of type `open_ended` is rendered
- **THEN** the UI displays a textarea for free-text input

#### Scenario: Render slider question

- **WHEN** a question of type `slider` is rendered
- **THEN** the UI displays a range input bounded by `min_value` and `max_value` with the given `step`

#### Scenario: Render ranking question

- **WHEN** a question of type `ranking` is rendered
- **THEN** the UI displays answer options in a reorderable list

### Requirement: Inline Suggestion Display

The UI SHALL display AI-generated suggestions alongside each question in the same view. Each
suggestion SHALL show the suggested answer, the LLM reasoning (if available), and all associated
citations (source and excerpt).

#### Scenario: Suggestion shown with citation

- **WHEN** the suggestion engine returns a suggestion with one or more citations for a question
- **THEN** the UI renders the suggestion text and a citation block per source
- **AND** the citation block includes the source identifier and the relevant excerpt

#### Scenario: Suggestion shown without citation

- **WHEN** the suggestion engine returns a suggestion with no citations
- **THEN** the UI renders the suggestion text and reasoning (if present) without a citation block

### Requirement: User Review and Edit

The UI SHALL allow respondents to accept, edit, or dismiss each suggestion independently before
any responses are submitted or stored.

#### Scenario: Accept suggestion

- **WHEN** a respondent clicks "Accept" on a suggestion
- **THEN** the corresponding form input is pre-filled with the suggested answer
- **AND** the suggestion block is visually marked as accepted

#### Scenario: Edit suggestion

- **WHEN** a respondent edits the form input after a suggestion has been accepted
- **THEN** the edited value is retained and the suggestion block reflects the modified state

#### Scenario: Dismiss suggestion

- **WHEN** a respondent clicks "Dismiss" on a suggestion
- **THEN** the suggestion block is hidden and the form input remains blank

### Requirement: Conditional Submit

The UI SHALL show a submit button only when the active adapter reports `"submit"` in its
capabilities. When submission is not supported, the UI SHALL operate in display-only mode.

#### Scenario: Submit available

- **WHEN** the adapter for the current survey reports `"submit"` capability
- **THEN** the UI renders a submit button at the end of the survey form

#### Scenario: Display-only mode

- **WHEN** the adapter for the current survey does NOT report `"submit"` capability
- **THEN** the UI renders a visible banner stating that programmatic submission is not available
  for this platform
- **AND** no submit button is shown
- **AND** the respondent can still review suggestions and manually fill in the external form

### Requirement: File Upload Entry Point

The UI SHALL provide a file upload flow as an alternative to entering a survey ID. Uploading a
survey file implies display-only mode — no API credentials are available, so `"submit"` is never
in capabilities for file-imported surveys. The UI SHALL make this limitation clear at upload time.

#### Scenario: File upload initiates display-only session

- **WHEN** a respondent uploads a survey file and selects its format (e.g. QSF, LSS)
- **THEN** the UI posts the file to `POST /surveys/import` and receives a survey ID
- **AND** the resulting session operates in display-only mode with the submission banner shown

#### Scenario: Unsupported file format

- **WHEN** a respondent uploads a file in a format not recognised by any adapter
- **THEN** the UI displays a clear error message listing the supported formats
- **AND** the respondent can try again without losing their file selection

### Requirement: Review State Persistence

The UI SHALL persist each respondent's review state (accepted, edited, dismissed, or pending)
per question in browser localStorage, keyed by session ID. State SHALL be written on every
accept, edit, or dismiss action without requiring a server round-trip or explicit user action.

#### Scenario: Auto-save on interaction

- **WHEN** a respondent accepts, edits, or dismisses a suggestion
- **THEN** the updated state for that question is immediately written to localStorage
- **AND** no explicit "save" action is required from the respondent

#### Scenario: Resume interrupted review

- **WHEN** a respondent returns to their session URL after leaving mid-review
- **THEN** the UI reads the saved state from localStorage on page load
- **AND** each question reflects its last saved status (accepted value pre-filled, dismissed
  suggestions hidden, pending questions shown fresh)

#### Scenario: Session expiry on resume

- **WHEN** a respondent returns to a session URL but the server session has expired
- **THEN** the UI displays a clear expiry message (detected via API response)
- **AND** the local review state is discarded
- **AND** the respondent is offered the option to start a new session for the same survey

#### Scenario: Local state cleared

- **WHEN** a respondent returns to a session URL but localStorage has been cleared
  (e.g. private browsing, manual clear)
- **THEN** the UI renders all questions in pending state with suggestions shown fresh
- **AND** no error is shown — loss of review state is a known, accepted trade-off

### Requirement: Document Upload

The UI SHALL allow respondents to upload one or more source documents (e.g. PDFs, Word files)
before reviewing suggestions. Uploaded documents are forwarded to the M-Autofill document
ingestion API; the UI SHALL NOT process or store document content itself. Document upload is
optional — respondents may skip it and proceed with suggestions derived from previously ingested
documents.

#### Scenario: Document uploaded successfully

- **WHEN** a respondent uploads one or more documents on the document upload step
- **THEN** the UI posts each file to the M-Autofill document ingestion API endpoint
- **AND** proceeds to the survey review page once all uploads are confirmed
- **AND** the UI does not retain or process the document content locally

#### Scenario: Document upload skipped

- **WHEN** a respondent skips the document upload step
- **THEN** the UI proceeds directly to the survey review page
- **AND** suggestions are generated from any documents already ingested for the session

#### Scenario: Unsupported document format

- **WHEN** a respondent uploads a file in a format not accepted by the ingestion API
- **THEN** the UI displays a clear error identifying the rejected file
- **AND** the respondent can remove it and retry without losing other uploaded files

#### Scenario: Document upload failure

- **WHEN** the ingestion API returns an error for an uploaded file
- **THEN** the UI displays an inline error for the failed file
- **AND** allows the respondent to retry or skip that file without restarting the flow

### Requirement: Response Submission

When the respondent submits the completed form, the UI SHALL send all responses to the M-Autofill
API, which delegates to the adapter's `submit_responses()`. The UI SHALL display a clear success
or error state after the submission attempt.

#### Scenario: Successful submission

- **WHEN** the respondent clicks submit and all required questions are answered
- **THEN** the UI POSTs the responses to the M-Autofill submit endpoint
- **AND** displays a confirmation page on success

#### Scenario: Submission error

- **WHEN** the submit call fails (network error or platform API error)
- **THEN** the UI displays an error message without losing the respondent's filled-in answers
- **AND** allows the respondent to retry

### Requirement: Paste Text Snippet on Documents Page

The UI SHALL provide a textarea on the document upload page so users can type or paste
plain text as context for answer suggestions, as an alternative or supplement to file uploads.

An optional label field SHALL allow users to name the snippet (e.g. "My CV", "Project notes").
When omitted the backend applies a default label.

#### Scenario: Submit text snippet

- **WHEN** the user types or pastes text into the textarea and submits the form
- **THEN** the text is sent to `POST /upload-text` and ingested into the session

#### Scenario: Text field is optional

- **WHEN** the user submits the form with an empty textarea
- **THEN** the text field is ignored and only file uploads (if any) are processed

#### Scenario: File upload and text snippet combined

- **WHEN** the user both selects files and fills in the textarea before submitting
- **THEN** both the files and the text snippet are ingested into the session

### Requirement: Live API Import Form

The UI SHALL provide a distinct "Import from Platform API" section on the survey upload
page as an alternative to file upload, supporting LimeSurvey and Qualtrics platforms.

The section SHALL display a prominent security warning informing the user that their
platform credentials will be transmitted to the server and that file upload is the
recommended approach.

Credential fields SHALL be conditional: selecting "LimeSurvey" shows API URL, username,
password, and survey ID fields; selecting "Qualtrics" shows API token, datacenter ID, and
survey ID fields.

#### Scenario: Successful API import via UI

- **WHEN** the user selects a platform, fills in valid credentials and survey ID, and submits
- **THEN** the form posts to the server, the survey is imported, and the user is redirected
  to the document upload step (same flow as file import)

#### Scenario: API import error shown in UI

- **WHEN** the server returns an error (400, 502, etc.)
- **THEN** the upload page is re-rendered with a descriptive error message and the form
  fields retain their previous values (except password fields, which are cleared)

#### Scenario: Security warning visible before credential fields

- **WHEN** the user views the upload page
- **THEN** the security warning is visible before any credential input fields are shown,
  regardless of which platform is selected

### Requirement: Answer Report Page

The UI SHALL provide a dedicated answer report page rendering the session's suggestion
results in a human-readable format. Each suggestion SHALL be presented as a card showing:
question text, suggested answer, reasoning (when available), and cited sources with
document name, position, and excerpt.

A "Download as JSON" link SHALL allow the user to save the raw report file.

#### Scenario: Report page renders all suggestions

- **WHEN** the user navigates to the answer report page after suggestions have been generated
- **THEN** one card per question is displayed with answer, reasoning, and citation details

#### Scenario: Report page with no suggestions

- **WHEN** the user navigates to the answer report page before any suggestion has been generated
- **THEN** an informative message is shown explaining that no suggestions are available yet

---

### Requirement: Answer Report Links on Review and Submission Pages

The UI SHALL provide a link to the answer report page on the survey review page and on
the submission confirmation page, so users can access their evidence trail before
deleting their session.

#### Scenario: Link visible on review page

- **WHEN** the user is on the survey review page
- **THEN** a "View answer report" link is visible linking to the report page

#### Scenario: Link visible on submission confirmation

- **WHEN** the user reaches the submission confirmation page
- **THEN** a "View answer report" link is visible before the session cleanup prompt

