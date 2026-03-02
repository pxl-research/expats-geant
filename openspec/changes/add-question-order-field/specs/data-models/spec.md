## MODIFIED Requirements

### Requirement: Question Model

The system SHALL define a Question model supporting five core QTI 3.0-compatible question types for MVP.
The Question model SHALL include an `order` field (integer, default 0) representing the display position
of the question within its section, consistent with the `order` field on the Section model.

#### Scenario: Multiple choice question

- **WHEN** a question is of type multiple_choice
- **THEN** it contains answer_options with text and identifiers

#### Scenario: Single choice question

- **WHEN** a question is of type single_choice
- **THEN** it contains exactly one correct answer_option

#### Scenario: Open-ended question

- **WHEN** a question is of type open_ended
- **THEN** it accepts free-text responses without predefined options

#### Scenario: Ranking question

- **WHEN** a question is of type ranking
- **THEN** it contains orderable answer_options

#### Scenario: Question order preserved on round-trip

- **WHEN** a survey is imported from a platform that supplies question ordering (e.g. LimeSurvey, SurveyMonkey)
- **THEN** each Question's `order` field reflects the platform-native position
- **AND** exporting the survey back to the same platform reproduces the original question sequence
