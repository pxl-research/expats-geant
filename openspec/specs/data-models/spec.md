# Capability: Data Models

## Purpose

Core domain models shared across M-Chat and M-Autofill.

## Requirements

### Requirement: Survey Model

The system SHALL define a Survey model representing a questionnaire with sections and questions.

#### Scenario: Survey with sections

- **WHEN** a survey is created with sections
- **THEN** each section contains questions with metadata

### Requirement: Question Model

The system SHALL define a Question model supporting four core QTI 3.0-compatible question types for MVP.

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

- MVP scope: Four core QTI question types (multiple_choice, single_choice, open_ended, ranking)
- No support for exotic QTI types, media types, or complex conditional logic in MVP
- All models located in `m_shared/models/`
