## MODIFIED Requirements

### Requirement: Survey Model

The system SHALL define a `Survey` model as the **platform-agnostic common denominator** for questionnaire data, informed by QTI 3.0 (question structure) and DDI (metadata and response documentation) but not bound to either standard. Platform-specific fields that do not map to the common model SHALL be preserved in a `metadata` dict to avoid data loss during import/export.

#### Scenario: Survey with sections

- **WHEN** a survey is created with sections
- **THEN** each section contains questions with metadata

#### Scenario: Platform-specific fields preserved

- **WHEN** a questionnaire is imported from a platform with fields not in the common model
- **THEN** those fields are stored in the `metadata` dict on the relevant model
- **AND** they are available for round-trip export back to the originating platform

### Requirement: Question Model

The system SHALL define a `Question` model supporting the five core question types that represent the common denominator across QTI 3.0, Qualtrics, LimeSurvey, and SurveyMonkey. The `metadata` dict SHALL serve as the escape hatch for platform-specific question properties.

#### Scenario: Multiple choice question

- **WHEN** a question is of type `multiple_choice`
- **THEN** it contains `answer_options` with text and identifiers

#### Scenario: Single choice question

- **WHEN** a question is of type `single_choice`
- **THEN** it contains exactly one selectable answer option (covers Likert scales, yes/no, dropdowns)

#### Scenario: Open-ended question

- **WHEN** a question is of type `open_ended`
- **THEN** it accepts free-text responses without predefined options

#### Scenario: Ranking question

- **WHEN** a question is of type `ranking`
- **THEN** it contains orderable `answer_options`

#### Scenario: Slider question

- **WHEN** a question is of type `slider`
- **THEN** it contains `min_value`, `max_value`, and `step`
