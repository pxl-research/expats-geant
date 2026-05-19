# answer-report Specification

## Purpose
Tracks per-session suggestion results (question, answer, reasoning, citations) in a
persistent `answer_report.json` file. Gives respondents a downloadable audit trail of
all AI-generated answers and their evidence sources. The report is scoped to the session
and deleted with it, in line with the platform's data-minimization principles.
## Requirements
### Requirement: Persist Suggestion Results

The system SHALL append the full suggestion result to a per-session answer report file
each time a suggestion is successfully generated. The report SHALL capture: question
text, suggested answer, reasoning (when provided by the LLM), and citations including
source document name, position, and excerpt.

The report file SHALL be stored in the session directory and deleted when the session
is deleted, consistent with all other session data.

#### Scenario: First suggestion creates report file

- **WHEN** the first suggestion is generated for a session
- **THEN** an `answer_report.json` file is created in the session directory containing
  the suggestion result as a single-element array

#### Scenario: Subsequent suggestions accumulate

- **WHEN** additional suggestions are generated in the same session
- **THEN** each result is appended to the existing array

#### Scenario: Report deleted with session

- **WHEN** `DELETE /session` is called
- **THEN** the answer report file is removed along with all other session data

---

### Requirement: Answer Report Download Endpoint

The system SHALL expose `GET /answer-report/download` returning the session's answer
report as a downloadable JSON file. The endpoint SHALL return 404 if no suggestions
have been generated yet in the session.

When review state is available for the session, each suggestion entry in the report
SHALL be enriched with the respondent's review decision: `review_state` (accepted,
edited, or dismissed) and `final_value` (the respondent's answer, which may differ
from the original suggestion if edited). Questions with no review action (pending)
SHALL be included without review fields.

#### Scenario: Download report with suggestions

- **WHEN** at least one suggestion has been generated and the user calls
  `GET /answer-report/download`
- **THEN** the full report is returned as a JSON attachment

#### Scenario: Download report with review state

- **WHEN** suggestions have been generated and the respondent has reviewed some questions
- **THEN** each reviewed suggestion entry includes `review_state` and `final_value`
- **AND** unreviewed suggestions are included without review fields

#### Scenario: No suggestions yet

- **WHEN** `GET /answer-report/download` is called before any suggestion has been made
- **THEN** a 404 Not Found response is returned

