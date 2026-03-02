## ADDED Requirements

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
