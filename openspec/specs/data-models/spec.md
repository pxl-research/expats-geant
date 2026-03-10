# Capability: Data Models

## Purpose

Core domain models shared across M-Chat and M-Autofill.
## Requirements
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

### Requirement: Response Model

The system SHALL define a Response model capturing user answers with metadata.

#### Scenario: Response with answer value

- **WHEN** a response is recorded
- **THEN** it contains question_id, answer_value, and timestamp

### Requirement: Citation Model

The system SHALL define a Citation model for tracking sources in answer suggestions.

#### Scenario: Citation with source metadata

- **WHEN** a citation is created from a document chunk
- **THEN** it contains source_id, chunk_id, position/percentage, timestamp, and optional highlights

### Requirement: Session Model

The system SHALL define a Session model representing user session context with TTL.

#### Scenario: Session with expiration

- **WHEN** a session is created
- **THEN** it contains session_id, user_id, created_at, expires_at, and isolation scope

### Requirement: Pydantic Validation

The system SHALL implement all models using Pydantic for validation and JSON schema generation.

#### Scenario: Valid model serialization

- **WHEN** a model is serialized to JSON
- **THEN** it validates against Pydantic schema and includes type information

## Notes

- MVP scope: Five core question types (multiple_choice, single_choice, open_ended, ranking, slider)
- No support for exotic QTI types, media types, or complex conditional logic in MVP
- All models located in `m_shared/models/`
