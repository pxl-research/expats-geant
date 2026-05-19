## MODIFIED Requirements

### Requirement: Review State Persistence

The UI SHALL persist each respondent's review state (accepted, edited, dismissed, or
pending) per question to the Cue API via `PUT /review-state/{question_id}` on every
accept, edit, or dismiss action. The UI SHALL also continue writing state to browser
localStorage as an optimistic cache for instant UI feedback.

On page load, the UI SHALL fetch the server-side review state via `GET /review-state`
and use it as the source of truth. If server state is available, it takes precedence
over localStorage. If the server returns an empty state but localStorage has saved
data, the localStorage state is used as a fallback.

#### Scenario: Auto-save to server on interaction

- **WHEN** a respondent accepts, edits, or dismisses a suggestion
- **THEN** the updated state for that question is written to both the API and localStorage
- **AND** no explicit "save" action is required from the respondent

#### Scenario: Resume from server state

- **WHEN** a respondent returns to their session URL (same or different device/browser)
- **THEN** the UI fetches the review state from the API on page load
- **AND** each question reflects its last saved server-side status

#### Scenario: Fallback to localStorage when server state is empty

- **WHEN** the server returns an empty review state but localStorage has saved data
  (e.g. API writes failed transiently during the previous session)
- **THEN** the UI falls back to the localStorage state

#### Scenario: Session expiry on resume

- **WHEN** a respondent returns to a session URL but the server session has expired
- **THEN** the UI displays a clear expiry message (detected via API response)
- **AND** the local review state is discarded
- **AND** the respondent is offered the option to start a new session for the same survey

#### Scenario: API write failure handled gracefully

- **WHEN** the API call to save review state fails (network error, timeout)
- **THEN** the localStorage write still succeeds
- **AND** no error is shown to the respondent
- **AND** on next page load, the server state may be stale but localStorage preserves progress
