## ADDED Requirements

### Requirement: Element Ordering

The system SHALL represent the order of sections within a survey, and questions
within a section, solely by their position in the respective list
(`survey.sections`, `section.questions`). The `Question` and `Section` models
SHALL NOT define a separate `order` field, and no editable surface (patch model
or tool parameter) SHALL expose one. Any platform-specific position or order
value SHALL be derived from list index at export time, never stored as a
first-class model field.

#### Scenario: Order determined by list position

- **WHEN** a survey is rendered, exported, or summarised
- **THEN** sections and questions appear in their list order
- **AND** no separate order field influences the result

#### Scenario: No order field on the models

- **WHEN** a `Question` or `Section` is serialised
- **THEN** the output contains no `order` field

#### Scenario: Legacy drafts with a stray order key load cleanly

- **WHEN** a persisted draft containing an `order` key is loaded
- **THEN** the model validates successfully and the `order` key is ignored
