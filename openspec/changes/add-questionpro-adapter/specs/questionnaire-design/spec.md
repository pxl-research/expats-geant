## MODIFIED Requirements

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface
for all platform-specific adapters. Each adapter SHALL implement
`export_survey(survey: Survey) -> str` and `capabilities() -> set[str]`. The
`import_survey()`, `submit_responses()`, `create_survey()`, `fetch_survey()`,
and `export_responses()` methods are optional; the default base implementations
SHALL raise `NotImplementedError` with a message identifying the adapter and
the unsupported method. Callers SHALL inspect `capabilities()` to determine
which methods an adapter supports before invoking them. Primary adapters
for MVP: LimeSurvey, Qualtrics. Secondary adapters: SurveyMonkey, QTI 3.0,
QuestionPro.

Adapters SHALL treat list position as the authoritative order: `import_survey`
SHALL populate `survey.sections` and `section.questions` in the source's display
order, and `export_survey` SHALL derive any platform-specific position or order
value from list index. Adapters SHALL NOT rely on a stored `order` field on the
`Question` or `Section` models.

#### Scenario: Import via adapter

- **WHEN** a questionnaire file is submitted with a specified platform format
- **AND** the selected adapter advertises `"import"` in `capabilities()`
- **THEN** the corresponding adapter is selected and converts the file to the
  internal `Survey` model
- **AND** unmappable platform-specific fields are preserved in the `metadata` dict

#### Scenario: Export via adapter

- **WHEN** a questionnaire is exported with a specified target format
- **THEN** the corresponding adapter serializes the internal `Survey` model to the
  platform format
- **AND** fields present only in `metadata` that are relevant to the target
  platform are included

#### Scenario: Cross-platform round-trip

- **WHEN** a questionnaire is imported from platform A and exported to platform B
- **THEN** all questions, answer options, and section structure are preserved
- **AND** platform-specific fields not supported by platform B are gracefully
  dropped

#### Scenario: Round-trip preserves order via list position

- **WHEN** a survey whose source encodes a non-trivial question or section order
  is imported and then re-exported
- **THEN** the section and question order is preserved through list position
- **AND** the result does not depend on a stored `order` field

#### Scenario: Adapter without import_survey

- **WHEN** a caller invokes `import_survey()` on an adapter that does not
  advertise `"import"` in its `capabilities()` set
- **THEN** the call SHALL raise `NotImplementedError` with a message identifying
  the adapter class and naming the `"import"` capability the caller should
  check before invoking

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, `"responses_export"`. `"create"` indicates the adapter implements `create_survey()`; `"api_create"` additionally indicates that `create_survey()` pushes to a live platform API and returns a platform-assigned ID (as opposed to a file-export fallback). `"responses_export"` indicates the adapter implements `export_responses()` and the resulting bytes are consumable by the platform's first-party response importer (the file format is adapter-defined: LimeSurvey emits TSV in its VV shape; Qualtrics emits CSV). An adapter MAY omit `"import"` when the platform has no downloadable survey-definition file (QuestionPro).

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, and `"responses_export"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"`, `"api_create"`, or `"responses_export"`

#### Scenario: QuestionPro reports API-only capabilities

- **WHEN** `capabilities()` is called on a QuestionPro adapter
- **THEN** it returns a set containing `"export"`, `"submit"`, `"create"`, and `"api_create"`
- **AND** it does NOT contain `"import"` (QuestionPro has no downloadable survey-definition file)
- **AND** it does NOT contain `"responses_export"` (QuestionPro has no admin-UI response file importer)

#### Scenario: created_via reflects actual creation path

- **WHEN** `POST /create` succeeds for a LimeSurvey, Qualtrics, or QuestionPro adapter
- **THEN** the response contains `created_via: "api"` and a platform-assigned survey ID
- **WHEN** `POST /create` succeeds for a SurveyMonkey or QTI adapter
- **THEN** the response contains `created_via: "file_export"` and serialized file content

#### Scenario: responses_export advertised independently of submit

- **WHEN** the UI inspects `capabilities()` to decide which response-output
  affordances to render
- **THEN** the presence of `"responses_export"` enables a download button
  and the presence of `"submit"` enables an API-submit button,
  independently — an adapter MAY advertise one without the other

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

#### Scenario: Successful submission — QuestionPro

- **WHEN** `submit_responses()` is called on the QuestionPro adapter with a valid survey ID and response list
- **AND** the survey's `metadata["questionpro_id_map"]` contains the QuestionPro `questionID` and `answerID` values for every referenced internal question and choice
- **THEN** the adapter POSTs to `https://api.questionpro.{datacenter_id}/a/api/v2/surveys/{survey_id}/responses` with a body of shape `{"responseSet": [{"questionID": ..., "answerValues": [{"answerID": ..., "value": {"text": ...}}]}]}`
- **AND** returns without error on a 2xx response

#### Scenario: QuestionPro submission without ID map

- **WHEN** `submit_responses()` is called on the QuestionPro adapter with a survey whose `metadata` does not contain a `questionpro_id_map` entry
- **THEN** the adapter SHALL raise `RuntimeError` with a message naming the missing metadata key and instructing the caller to fetch or re-create the survey to populate it

#### Scenario: Submission not supported

- **WHEN** `submit_responses()` is called on an adapter that does not support it
- **THEN** `NotImplementedError` is raised with a message indicating the platform does not support response submission

### Requirement: Stateless Tool API

The system SHALL expose stateless REST endpoints for questionnaire operations that can be called without a session. `POST /import` SHALL parse a platform-format file and return a `Survey`. `POST /export` SHALL serialize a `Survey` to a specified platform format and return the file content. `POST /create` SHALL push a `Survey` to the target platform via its adapter and return the platform survey ID, or return the exported file content if the adapter does not support direct creation. These endpoints SHALL NOT require a `session_id` and SHALL be callable by institutional tools without session infrastructure.

The `POST /import` endpoint SHALL pre-check the selected adapter's capabilities and return 422 Unprocessable Entity when the adapter does not advertise the `"import"` capability, with a message naming the format and instructing the caller to use the API fetch endpoint (`POST /surveys/import-from-api`) instead.

#### Scenario: Import without session

- **WHEN** a platform file is submitted to `POST /import` without a session_id
- **AND** the selected adapter advertises `"import"` in `capabilities()`
- **THEN** the file is parsed and a `Survey` JSON is returned
- **AND** no session is created or modified

#### Scenario: Import for adapter without import capability

- **WHEN** a file is submitted to `POST /import` with a format whose adapter does not advertise `"import"` (e.g. `questionpro`)
- **THEN** the endpoint returns 422 Unprocessable Entity with a message naming the format and recommending the API fetch endpoint
- **AND** no parsing is attempted

#### Scenario: Create survey on platform

- **WHEN** a `Survey` and target format are submitted to `POST /create`
- **THEN** if the adapter supports direct creation, the survey is pushed to the platform
- **AND** the platform-assigned survey ID is returned

#### Scenario: Create survey as file download

- **WHEN** a `Survey` is submitted to `POST /create` with a format that does not support API creation
- **THEN** the serialized file content is returned as a download
