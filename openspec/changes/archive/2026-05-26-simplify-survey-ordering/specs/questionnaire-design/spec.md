## ADDED Requirements

### Requirement: Question and Section Reordering

The system SHALL provide operations to change the position of an existing
question or section without recreating it, exposed both as LLM tools
(`move_question`, `move_section`) and as HTTP endpoints
(`PATCH /chat/{session_id}/survey/questions/{question_id}/position` and
`PATCH /chat/{session_id}/survey/sections/{section_id}/position`).
`move_question` SHALL accept an optional `after_id` (place the question
immediately after that question; omitted = move to the start of the target
section) and an optional `section_id` (move the question into a different
section, preserving its id). `move_section` SHALL accept an optional `after_id`.
These operations SHALL change list position only and SHALL NOT alter any other
field.

#### Scenario: Reorder a question within its section

- **WHEN** `move_question` is called with an `after_id` in the same section
- **THEN** the question is positioned immediately after that question
- **AND** its id and all other fields are unchanged

#### Scenario: Move a question to the start of a section

- **WHEN** `move_question` is called with no `after_id`
- **THEN** the question is placed first in the target section

#### Scenario: Move a question to another section

- **WHEN** `move_question` is called with a `section_id` different from the
  question's current section
- **THEN** the question is removed from its current section and inserted into the
  target section, preserving its id

#### Scenario: Reorder a section

- **WHEN** `move_section` is called with an `after_id`
- **THEN** the section is positioned immediately after that section

#### Scenario: Move references an unknown id

- **WHEN** a move operation references a question or section id that does not
  exist
- **THEN** a not-found error (`question_not_found` or `section_not_found`) is
  returned and the draft is unchanged

## MODIFIED Requirements

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface
for all platform-specific adapters. Each adapter SHALL implement
`import_survey(raw: str) -> Survey`, `export_survey(survey: Survey) -> str`, and
`capabilities() -> set[str]`. The `submit_responses()` method is optional; the
default base implementation SHALL raise `NotImplementedError`. Primary adapters
for MVP: LimeSurvey, Qualtrics. Secondary adapters: SurveyMonkey, QTI 3.0.

Adapters SHALL treat list position as the authoritative order: `import_survey`
SHALL populate `survey.sections` and `section.questions` in the source's display
order, and `export_survey` SHALL derive any platform-specific position or order
value from list index. Adapters SHALL NOT rely on a stored `order` field on the
`Question` or `Section` models.

#### Scenario: Import via adapter

- **WHEN** a questionnaire file is submitted with a specified platform format
- **THEN** the corresponding adapter is selected and converts the file to the
  internal `Survey` model
- **AND** unmappable platform-specific fields are preserved in the `metadata` dict

#### Scenario: Export via adapter

- **WHEN** a questionnaire is exported with a specified target format
- **THEN** the corresponding adapter serializes the internal `Survey` model to the
  platform format
- **AND** fields present only in `metadata` that are relevant to the target
  platform are included

#### Scenario: Cross-platform round-trip

- **WHEN** a questionnaire is imported from platform A and exported to platform B
- **THEN** all questions, answer options, and section structure are preserved
- **AND** platform-specific fields not supported by platform B are gracefully
  dropped

#### Scenario: Round-trip preserves order via list position

- **WHEN** a survey whose source encodes a non-trivial question or section order
  is imported and then re-exported
- **THEN** the section and question order is preserved through list position
- **AND** the result does not depend on a stored `order` field
