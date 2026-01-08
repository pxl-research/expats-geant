# Capability: Questionnaire Design (M-Chat)

AI-powered assistant for survey administrators to create better questionnaires faster with guardrails, validation, and tagging.

## ADDED Requirements

### Requirement: Question Suggestion

The system SHALL generate improved versions of survey questions for clarity and consistency.

#### Scenario: Suggest reworded question

- **WHEN** an administrator requests a suggestion for a question
- **THEN** the system returns alternative phrasings with reasoning

#### Scenario: Suggest with style guide context

- **WHEN** a suggestion includes style guide context
- **THEN** the system enforces institutional style conventions in suggestions

### Requirement: Question Validation

The system SHALL check questions against style guidelines and basic grammar rules.

#### Scenario: Validate question clarity

- **WHEN** a question is validated
- **THEN** the system flags unclear, ambiguous, or biased phrasing

#### Scenario: Validate QTI compliance

- **WHEN** a questionnaire is validated
- **THEN** the system checks that all questions use supported QTI 3.0 types (multiple_choice, single_choice, open_ended, ranking)

### Requirement: Question Tagging

The system SHALL automatically suggest metadata tags for questions.

#### Scenario: Suggest tags for single question

- **WHEN** a question is provided
- **THEN** the system suggests relevant tags (e.g., topic, difficulty, question_type)

#### Scenario: Batch tagging for questionnaire

- **WHEN** multiple questions are tagged together
- **THEN** tags are suggested based on section context and question content

### Requirement: QTI 3.0 Import

The system SHALL parse QTI 3.0 XML and convert to internal questionnaire model.

#### Scenario: Import QTI questionnaire

- **WHEN** a QTI 3.0 XML file is imported
- **THEN** it is parsed and converted to Survey model with questions and sections

#### Scenario: Validate imported QTI compatibility

- **WHEN** a QTI file is imported
- **THEN** only supported question types are accepted; unsupported types are flagged

### Requirement: QTI 3.0 Export

The system SHALL convert internal questionnaire model to QTI 3.0 XML.

#### Scenario: Export questionnaire to QTI

- **WHEN** a questionnaire is exported
- **THEN** it is serialized to valid QTI 3.0 XML with all questions and metadata

## Notes

- MVP scope: Support four core QTI question types only (multiple_choice, single_choice, open_ended, ranking)
- No conditional branching logic in MVP
- LLM used for suggestions and validation; deterministic rule-based validation for compliance checks
- Located in `m_chat/suggestion_engine.py`, `validation_engine.py`, `tagging_engine.py`
- Integrated with data-models capability for Survey/Question representation
