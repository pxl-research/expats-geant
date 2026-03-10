# Capability: Questionnaire Design (M-Chat)

## Purpose

AI-powered assistant for survey administrators to create better questionnaires faster with guardrails, validation, and tagging.
## Requirements
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

#### Scenario: Validate QTI compliance (optional)

- **WHEN** a questionnaire is validated with the QTI adapter selected
- **THEN** the system checks that all questions use QTI 3.0-compatible types
- **AND** compliance is reported as an adapter-level concern, not a core validation failure

### Requirement: Question Tagging

The system SHALL automatically suggest metadata tags for questions.

#### Scenario: Suggest tags for single question

- **WHEN** a question is provided
- **THEN** the system suggests relevant tags (e.g., topic, difficulty, question_type)

#### Scenario: Batch tagging for questionnaire

- **WHEN** multiple questions are tagged together
- **THEN** tags are suggested based on section context and question content

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface for all platform-specific adapters. Each adapter SHALL implement `import_survey(raw: str) -> Survey`, `export_survey(survey: Survey) -> str`, and `capabilities() -> set[str]`. The `submit_responses()` method is optional; the default base implementation SHALL raise `NotImplementedError`. Primary adapters for MVP: LimeSurvey, Qualtrics. Secondary adapters: SurveyMonkey, QTI 3.0.

#### Scenario: Import via adapter

- **WHEN** a questionnaire file is submitted with a specified platform format
- **THEN** the corresponding adapter is selected and converts the file to the internal `Survey` model
- **AND** unmappable platform-specific fields are preserved in the `metadata` dict

#### Scenario: Export via adapter

- **WHEN** a questionnaire is exported with a specified target format
- **THEN** the corresponding adapter serializes the internal `Survey` model to the platform format
- **AND** fields present only in `metadata` that are relevant to the target platform are included

#### Scenario: Cross-platform round-trip

- **WHEN** a questionnaire is imported from platform A and exported to platform B
- **THEN** all questions, answer options, and section structure are preserved
- **AND** platform-specific fields not supported by platform B are gracefully dropped

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`.

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"submit"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"` and `"export"` but NOT `"submit"`

### Requirement: Response Submission via Adapter

Adapters that support response write-back SHALL implement `submit_responses(survey_id: str, responses: list[Response]) -> None`, which persists the provided responses to the originating platform via its API. Adapters that do not support submission SHALL leave this method as the base `NotImplementedError`.

#### Scenario: Successful submission — LimeSurvey

- **WHEN** `submit_responses()` is called on the LimeSurvey adapter with a valid survey ID and response list
- **THEN** the adapter authenticates with the LimeSurvey RemoteControl 2 API and calls `add_response` for each response
- **AND** returns without error on success

#### Scenario: Successful submission — Qualtrics

- **WHEN** `submit_responses()` is called on the Qualtrics adapter with a valid survey ID and response list
- **THEN** the adapter calls the Qualtrics Response Import API and POSTs the serialized responses
- **AND** returns without error on success

#### Scenario: Submission not supported

- **WHEN** `submit_responses()` is called on an adapter that does not support it
- **THEN** `NotImplementedError` is raised with a message indicating the platform does not support response submission

## Notes

- MVP scope: Support five core question types (multiple_choice, single_choice, open_ended, ranking, slider)
- No conditional branching logic in MVP
- LLM used for suggestions and validation; deterministic rule-based validation for compliance checks
- Located in `m_chat/suggestion_engine.py`, `validation_engine.py`, `tagging_engine.py`
- Integrated with data-models capability for Survey/Question representation
- Adapter `create` capability: platforms with a write API (LimeSurvey, Qualtrics) SHALL support `create_survey(survey: Survey) -> str` returning the platform-assigned survey ID; platforms without a write API (SurveyMonkey, QTI) SHALL respond to `create` by returning an exported file payload (i.e., a file download fallback)
