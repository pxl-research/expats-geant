## MODIFIED Requirements

### Requirement: Question Model

The system SHALL define a `Question` model supporting six core question types that represent the common denominator across QTI 3.0, Qualtrics, LimeSurvey, and SurveyMonkey. The `metadata` dict SHALL serve as the escape hatch for platform-specific question properties.

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

#### Scenario: Descriptive item

- **WHEN** a question is of type `descriptive`
- **THEN** it contains display text only, with no answer_options, no min/max, and `required` defaults to `False`
- **AND** it is rendered as static informational content in the UI
- **AND** no response is expected or collected for this item
