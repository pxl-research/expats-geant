## ADDED Requirements

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

#### Scenario: Download report with suggestions

- **WHEN** at least one suggestion has been generated and the user calls
  `GET /answer-report/download`
- **THEN** the full report is returned as a JSON attachment

#### Scenario: No suggestions yet

- **WHEN** `GET /answer-report/download` is called before any suggestion has been made
- **THEN** a 404 Not Found response is returned
