## MODIFIED Requirements

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface for all platform-specific adapters. Each adapter SHALL implement `import_survey(raw: str) -> Survey`, `export_survey(survey: Survey) -> str`, `create_survey(survey: Survey) -> str`, and `capabilities() -> set[str]`. The `submit_responses()` and `create_survey()` methods are optional; the default base implementation SHALL raise `NotImplementedError`. Primary adapters for MVP: LimeSurvey, Qualtrics. Secondary adapters: SurveyMonkey, QTI 3.0.

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

#### Scenario: Create survey via API-backed adapter

- **WHEN** `create_survey()` is called on LimeSurvey or Qualtrics adapter
- **THEN** the adapter pushes the survey to the platform via its write API
- **AND** returns the platform-assigned survey ID as a string

#### Scenario: Create survey via file-download fallback

- **WHEN** `create_survey()` is called on SurveyMonkey or QTI adapter
- **THEN** the adapter returns the serialized file content (same as `export_survey()`)
- **AND** the caller is responsible for presenting the file as a download

## MODIFIED Requirements

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`.

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, and `"create"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"`

## ADDED Requirements

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
