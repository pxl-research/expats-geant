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

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`. `"create"` indicates the adapter implements `create_survey()`; `"api_create"` additionally indicates that `create_survey()` pushes to a live platform API and returns a platform-assigned ID (as opposed to a file-export fallback).

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, `"create"`, and `"api_create"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"` or `"api_create"`

#### Scenario: created_via reflects actual creation path

- **WHEN** `POST /create` succeeds for a LimeSurvey or Qualtrics adapter
- **THEN** the response contains `created_via: "api"` and a platform-assigned survey ID
- **WHEN** `POST /create` succeeds for a SurveyMonkey or QTI adapter
- **THEN** the response contains `created_via: "file_export"` and serialized file content

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

### Requirement: Stateless Tool API

The system SHALL expose stateless REST endpoints for questionnaire operations that can be called without a session. `POST /import` SHALL parse a platform-format file and return a `Survey`. `POST /export` SHALL serialize a `Survey` to a specified platform format and return the file content. `POST /create` SHALL push a `Survey` to the target platform via its adapter and return the platform survey ID, or return the exported file content if the adapter does not support direct creation. These endpoints SHALL NOT require a `session_id` and SHALL be callable by institutional tools without session infrastructure.

#### Scenario: Import without session

- **WHEN** a platform file is submitted to `POST /import` without a session_id
- **THEN** the file is parsed and a `Survey` JSON is returned
- **AND** no session is created or modified

#### Scenario: Create survey on platform

- **WHEN** a `Survey` and target format are submitted to `POST /create`
- **THEN** if the adapter supports direct creation, the survey is pushed to the platform
- **AND** the platform-assigned survey ID is returned

#### Scenario: Create survey as file download

- **WHEN** a `Survey` is submitted to `POST /create` with a format that does not support API creation
- **THEN** the serialized file content is returned as a download

### Requirement: Context-Aware Tool Endpoints

The system SHALL provide `POST /suggest`, `POST /validate`, and `POST /tag` endpoints that operate in two modes depending on whether a `session_id` is provided. Without a `session_id` the endpoints SHALL perform generic single-question reasoning. With a `session_id` the endpoints SHALL load the session's draft survey and tag vocabulary to produce survey-aware output.

#### Scenario: Suggest without session

- **WHEN** a question is submitted to `POST /suggest` without a session_id
- **THEN** alternative phrasings with reasoning are returned based on the question text alone

#### Scenario: Suggest with session context

- **WHEN** a question is submitted to `POST /suggest` with a valid session_id
- **THEN** the suggestion incorporates the survey topic, audience, and existing questions from the session draft

#### Scenario: Tag with session vocabulary

- **WHEN** a question is submitted to `POST /tag` with a valid session_id
- **THEN** the returned tags prefer reuse of tags already present in the session's tag vocabulary
- **AND** the session's tag vocabulary is updated with any new tags introduced

#### Scenario: Validate full session draft

- **WHEN** `POST /validate` is called with a session_id and no explicit survey payload
- **THEN** the full draft survey from the session is validated
- **AND** issues are returned with question-level references

### Requirement: Conversational Session API

The system SHALL provide a session-scoped conversational API for iterative questionnaire authoring. `POST /chat/sessions` SHALL create a new chat session linked to the authenticated user and return a `session_id`. `GET /chat/sessions` SHALL list the user's active sessions. `POST /chat/{session_id}` SHALL accept a user message, update the draft survey based on the LLM response, and return the assistant message and whether the survey was updated. `GET /chat/{session_id}/survey` SHALL return the current draft `Survey`. `POST /chat/{session_id}/reset` SHALL clear the draft survey and tag vocabulary while preserving conversation history and documents. `DELETE /chat/{session_id}` SHALL end the session and wipe all session files. The LLM SHALL use server-side orchestration to call internal tool endpoints as needed; no client-side tool execution is required.

#### Scenario: Start new chat session

- **WHEN** `POST /chat/sessions` is called by an authenticated user
- **THEN** a new session is created with an empty draft survey, default style profile, and empty tag vocabulary
- **AND** the session_id is returned

#### Scenario: Iterative question authoring

- **WHEN** a user message is sent to `POST /chat/{session_id}`
- **THEN** the LLM responds based on conversation history and the current draft survey
- **AND** if the LLM proposes changes to the survey, the draft is updated in the session
- **AND** `survey_updated: true` is returned when the draft changes

#### Scenario: Session isolation

- **WHEN** two users have active chat sessions
- **THEN** each session's draft survey, tag vocabulary, conversation history, and style profile are fully isolated

#### Scenario: Session resume

- **WHEN** an authenticated user reconnects within the session TTL window
- **THEN** the session state (draft, vocabulary, history, style profile) is fully restored

### Requirement: Document Upload for Survey Drafting

The system SHALL allow administrators to upload source documents (PPTX, DOCX, PDF, TXT) to a chat session. The system SHALL extract text from the uploaded file and identify topics and structural elements that can inform an initial survey draft. The LLM SHALL use the extracted content as context in subsequent chat turns to propose relevant questions.

#### Scenario: Upload slide deck to session

- **WHEN** a PPTX file is uploaded to `POST /chat/{session_id}/upload`
- **THEN** text is extracted from the slides
- **AND** a topic summary is returned
- **AND** the extracted content is available as context in subsequent chat turns

#### Scenario: LLM proposes survey from uploaded document

- **WHEN** a document has been uploaded and the user asks the LLM to draft a survey
- **THEN** the LLM proposes a section structure and initial questions informed by the document content
- **AND** the draft survey is updated in the session

### Requirement: Session Style Profile and Language

The system SHALL maintain a style profile per M-Chat session that influences all LLM-generated suggestions, validation feedback, and generated question text. The style profile SHALL include: a `language` field (ISO 639-1, default `"en"`), a `free_text` field for admin-typed style preferences, and a `document_summary` field populated when the admin uploads an institutional style guide document. If no style preferences are provided, the system SHALL apply sensible defaults: English language, neutral formal tone, and rules from the platform's survey design guidelines. The style profile SHALL persist for the lifetime of the session and survive session resume. The admin SHALL be able to update the language or free-text preference at any point during the session.

#### Scenario: Default style profile applied

- **WHEN** a new chat session is created without any style input
- **THEN** the style profile defaults to English language and neutral formal tone
- **AND** `defaults_applied` is set to `true` in the stored profile

#### Scenario: Admin sets language

- **WHEN** the admin updates the session language to a non-default value (e.g. `"nl"`)
- **THEN** all subsequent suggestions, validation messages, and generated questions are produced in that language
- **AND** the language setting persists across session resume

#### Scenario: Admin types style preferences

- **WHEN** the admin provides free-text style preferences (e.g. "formal tone, 5-point scales only")
- **THEN** the LLM incorporates these preferences in all subsequent suggestions and validation feedback

#### Scenario: Admin uploads institutional style guide

- **WHEN** an institutional style guide document is uploaded to the session
- **THEN** the document text is extracted and the LLM generates a concise summary of the style rules
- **AND** the summary is stored in the session style profile and used as context on all subsequent turns

### Requirement: Methodological Advisor Behaviour

During conversational survey design, the system SHALL proactively surface methodological
concerns after each edit that introduces a new issue, and SHALL ask the designer whether
the choice is intentional. The system SHALL NOT lecture unprompted on minor edits or
re-raise concerns that were already present before the edit.

The advisory behaviour SHALL be powered by the tier-1 validation engine (deterministic,
no extra LLM call per turn). At most two newly introduced issues SHALL be surfaced per
turn to avoid reply flooding. Each issue SHALL be framed as a brief observation followed
by "— was this intentional?" rather than as an instruction or criticism.

This requirement extends `Question Validation` (on-demand) with a proactive, in-context
advisory layer. The `/validate` endpoint behaviour is unchanged.

#### Scenario: Advisory note after introducing a new issue

- **WHEN** a chat turn produces a survey update that introduces one or more new
  validation warnings
- **THEN** the assistant reply includes a brief advisory note for up to two of the new
  issues, each phrased as an observation with "— was this intentional?"

#### Scenario: No advisory note when no new issues

- **WHEN** a chat turn produces a survey update but introduces no new validation issues
- **THEN** no advisory note is appended to the reply

#### Scenario: Pre-existing issues are not re-raised

- **WHEN** a survey update does not change the set of validation issues
- **THEN** the assistant does not mention those issues in the reply

---

### Requirement: Extended Tier-1 Methodological Checks

The deterministic validation tier SHALL include the following additional checks, all at
`warning` or `info` severity:

- **`social_desirability`** (warning): question text uses phrasing that implies a
  virtuous or socially expected answer (e.g. "do you regularly", "do you always",
  "do you make sure to")
- **`missing_neutral_option`** (info): a `single_choice` question has an even number
  of options and none of them contain a neutral-signalling label ("neither", "neutral",
  "no opinion", "n/a", "not applicable") — the scale forces a directional response
- **`unbalanced_anchors`** (warning): all answer options (three or more) lean the same
  sentiment direction, suggesting the scale is not balanced around a midpoint
- **`survey_fatigue`** (warning): the total number of questions across all sections
  exceeds the configured threshold (default: 30)

These checks complement the existing `double_barreled`, `leading_language`,
`scale_too_short`, `scale_too_long`, and `likert_unlabelled` checks.

#### Scenario: Social desirability flagged

- **WHEN** a question text contains phrasing that implies an expected virtuous answer
- **THEN** a `social_desirability` warning is returned by `validate_question()`

#### Scenario: Missing neutral option flagged

- **WHEN** a `single_choice` question has an even number of options with no neutral label
- **THEN** a `missing_neutral_option` info issue is returned

#### Scenario: Unbalanced anchors flagged

- **WHEN** all answer options in a scale lean the same sentiment direction
- **THEN** an `unbalanced_anchors` warning is returned

#### Scenario: Survey fatigue flagged

- **WHEN** the total question count across all sections exceeds the threshold
- **THEN** a `survey_fatigue` warning is returned by `validate_survey()`

#### Scenario: Clean question produces no new issues

- **WHEN** a well-formed, balanced question is validated
- **THEN** none of the new checks fire

## Notes

- MVP scope: Support five core question types (multiple_choice, single_choice, open_ended, ranking, slider)
- No conditional branching logic in MVP
- LLM used for suggestions and validation; deterministic rule-based validation for compliance checks
- Located in `m_chat/suggestion_engine.py`, `validation_engine.py`, `tagging_engine.py`
- Integrated with data-models capability for Survey/Question representation
- Adapter `create` capability: platforms with a write API (LimeSurvey, Qualtrics) SHALL support `create_survey(survey: Survey) -> str` returning the platform-assigned survey ID; platforms without a write API (SurveyMonkey, QTI) SHALL respond to `create` by returning an exported file payload (i.e., a file download fallback)
