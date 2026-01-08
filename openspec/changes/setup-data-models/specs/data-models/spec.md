# Capability: Data Models

Core domain models shared across M-Chat and M-Autofill.

## ADDED Requirements

### Requirement: Survey Model

The system SHALL define a Survey model representing a questionnaire with sections and metadata.

#### Scenario: Survey with sections

- **WHEN** a survey is created with sections
- **THEN** it contains an array of Section objects with ordering and metadata

### Requirement: Section Model

The system SHALL define a Section model representing a page or grouping within a survey.

#### Scenario: Section with questions

- **WHEN** a section is created
- **THEN** it contains title, description, and an array of Question objects

### Requirement: Question Model

The system SHALL define a Question model supporting five core QTI 3.0-compatible question types for MVP.

#### Scenario: Multiple choice question

- **WHEN** a question is of type multiple_choice
- **THEN** it contains answer_options with text and identifiers

#### Scenario: Single choice question

- **WHEN** a question is of type single_choice
- **THEN** it contains answer_options; can represent discrete scales (Likert 1-5) or yes/no choices

#### Scenario: Open-ended question

- **WHEN** a question is of type open_ended
- **THEN** it accepts free-text responses without predefined options

#### Scenario: Ranking question

- **WHEN** a question is of type ranking
- **THEN** it contains orderable answer_options

#### Scenario: Slider question

- **WHEN** a question is of type slider
- **THEN** it contains min_value, max_value, and optional step; represents continuous numeric ranges

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

- MVP scope: Five core QTI question types (multiple_choice, single_choice, open_ended, ranking, slider)
- Scale/Likert questions: use `single_choice` with numeric/semantic options or `slider` for continuous scales
- No support for exotic QTI types, media types, or complex conditional logic in MVP
- Section model enables survey pagination and logical grouping
- All models located in `m_shared/models/`
