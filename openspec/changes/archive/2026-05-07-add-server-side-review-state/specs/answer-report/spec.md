## MODIFIED Requirements

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
