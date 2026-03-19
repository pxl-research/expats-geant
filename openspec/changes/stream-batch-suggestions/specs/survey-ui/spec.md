## MODIFIED Requirements

### Requirement: API Separation

The survey UI SHALL be a standalone module (`m_ui/`) that communicates with the M-Autofill
core system exclusively via its public HTTP API. The UI SHALL NOT import Python modules from
`m_autofill/` or `m_shared/` directly.

#### Scenario: UI calls API for survey data

- **WHEN** the UI needs to render a survey
- **THEN** it calls `GET /surveys/{survey_id}` on the M-Autofill API
- **AND** does not access the internal database or model layer directly

#### Scenario: UI streams suggestions via SSE proxy

- **WHEN** the UI needs to populate suggestions for a survey session
- **THEN** the browser connects to the m-ui SSE proxy endpoint `GET /session/{id}/suggest-stream`
- **AND** m-ui forwards the request to `POST /suggest/stream` on M-Autofill, injecting the auth token
- **AND** each suggestion event is re-rendered as HTML and forwarded to the browser as it arrives
- **AND** the UI does not call the bulk `POST /suggest/batch` endpoint for the review page

### Requirement: Inline Suggestion Display

The UI SHALL display AI-generated suggestions alongside each question in the same view,
rendering each suggestion as soon as it is received from the SSE stream. Each suggestion
SHALL show the suggested answer, the LLM reasoning (if available), and all associated
citations (source and excerpt).

#### Scenario: Suggestions appear progressively

- **WHEN** the review page loads
- **THEN** the UI connects to the SSE stream endpoint
- **AND** each suggestion is rendered into its corresponding question zone as it arrives
- **AND** questions without a suggestion yet show a per-question loading indicator
- **AND** the page is interactive throughout — the respondent does not need to wait for all suggestions

#### Scenario: Suggestion shown with citation

- **WHEN** the suggestion engine returns a suggestion with one or more citations for a question
- **THEN** the UI renders the suggestion text and a citation block per source
- **AND** the citation block includes the source identifier and the relevant excerpt

#### Scenario: Suggestion shown without citation

- **WHEN** the suggestion engine returns a suggestion with no citations
- **THEN** the UI renders the suggestion text and reasoning (if present) without a citation block

#### Scenario: Stream error shown inline

- **WHEN** the SSE stream closes with an error before all suggestions have been delivered
- **THEN** questions that did not receive a suggestion display an inline error message
- **AND** questions that already received a suggestion are unaffected
