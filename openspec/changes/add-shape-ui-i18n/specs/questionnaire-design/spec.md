## MODIFIED Requirements

### Requirement: Conversational Session API

The system SHALL provide a session-scoped conversational API for iterative questionnaire
authoring. `POST /chat/sessions` SHALL create a new chat session linked to the
authenticated user and return a `session_id`. `GET /chat/sessions` SHALL list the user's
active sessions. `POST /chat/{session_id}` SHALL accept a user message, update the draft
survey based on the LLM response, and return the assistant message and whether the survey
was updated. When a survey update introduces new validation issues, the response SHALL
include them as structured data in a `validation_issues` array rather than injecting
English text into the reply. Each issue SHALL contain `code`, `message` (English),
`severity`, and `question_id` fields. `GET /chat/{session_id}/survey` SHALL return the
current draft `Survey`. `POST /chat/{session_id}/reset` SHALL clear the draft survey and
tag vocabulary while preserving conversation history and documents.
`DELETE /chat/{session_id}` SHALL end the session and wipe all session files. The LLM
SHALL use server-side orchestration to call internal tool endpoints as needed; no
client-side tool execution is required.

#### Scenario: Start new chat session

- **WHEN** `POST /chat/sessions` is called by an authenticated user
- **THEN** a new session is created with an empty draft survey, default style profile, and empty tag vocabulary
- **AND** the session_id is returned

#### Scenario: Iterative question authoring

- **WHEN** a user message is sent to `POST /chat/{session_id}`
- **THEN** the LLM responds based on conversation history and the current draft survey
- **AND** if the LLM proposes changes to the survey, the draft is updated in the session
- **AND** `survey_updated: true` is returned when the draft changes

#### Scenario: Validation issues returned as structured data

- **WHEN** a chat turn produces a survey update that introduces new validation warnings
- **THEN** the response includes a `validation_issues` array with each issue containing
  `code`, `message`, `severity`, and `question_id`
- **AND** the issues are NOT injected as text into the `reply` field

#### Scenario: No validation issues when none introduced

- **WHEN** a chat turn produces a survey update that introduces no new validation issues
- **THEN** the `validation_issues` array is empty or absent

#### Scenario: Session isolation

- **WHEN** two users have active chat sessions
- **THEN** each session's draft survey, tag vocabulary, conversation history, and style profile are fully isolated

#### Scenario: Session resume

- **WHEN** an authenticated user reconnects within the session TTL window
- **THEN** the session state (draft, vocabulary, history, style profile) is fully restored

### Requirement: Methodological Advisor Behaviour

During conversational survey design, the system SHALL proactively surface methodological
concerns after each edit that introduces a new issue by returning them as structured
validation issues in the chat response. The system SHALL NOT inject advisory text into
the LLM reply string. The system SHALL NOT re-raise concerns that were already present
before the edit.

The advisory behaviour SHALL be powered by the tier-1 validation engine (deterministic,
no extra LLM call per turn). At most two newly introduced issues SHALL be included in
the `validation_issues` response field per turn to avoid overwhelming the user.

This requirement extends `Question Validation` (on-demand) with a proactive, in-context
advisory layer. The `/validate` endpoint behaviour is unchanged.

#### Scenario: Advisory note after introducing a new issue

- **WHEN** a chat turn produces a survey update that introduces one or more new
  validation warnings
- **THEN** the response includes up to two of the new issues in the `validation_issues`
  array with their `code`, `message`, `severity`, and `question_id`

#### Scenario: No advisory note when no new issues

- **WHEN** a chat turn produces a survey update but introduces no new validation issues
- **THEN** the `validation_issues` array is empty or absent

#### Scenario: Pre-existing issues are not re-raised

- **WHEN** a survey update does not change the set of validation issues
- **THEN** previously existing issues are not included in `validation_issues`

### Requirement: API Error Code Convention

All Shape API error responses (HTTP 4xx/5xx) SHALL include a stable `code` string field
in the error detail alongside the existing English `message` field. Error codes SHALL
use snake_case identifiers (e.g. `session_not_found`, `file_too_large`,
`oidc_not_configured`). This enables frontend clients to translate error messages
independently of the API's English text.

#### Scenario: Error response includes code and message

- **WHEN** an API request fails with a 404 for a missing session
- **THEN** the response body contains `{"detail": {"code": "session_not_found", "message": "Session not found or access denied."}}`

#### Scenario: Existing API consumers unaffected

- **WHEN** an API consumer reads the `detail` field as a string (legacy behaviour)
- **THEN** the response is still parseable (the `message` field provides the English text)
