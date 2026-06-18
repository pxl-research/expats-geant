# Capability: Questionnaire Design (Shape)

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

#### Scenario: Suggest descriptive block text

- **WHEN** an administrator requests a suggestion for a descriptive item
- **THEN** the system treats it as informational text (not a question) and suggests improved wording appropriate for introductions, instructions, or contextual information

### Requirement: Question Validation

The system SHALL check questions against style guidelines and basic grammar rules.

#### Scenario: Validate question clarity

- **WHEN** a question is validated
- **THEN** the system flags unclear, ambiguous, or biased phrasing

#### Scenario: Validate QTI compliance (optional)

- **WHEN** a questionnaire is validated with the QTI adapter selected
- **THEN** the system checks that all questions use QTI 3.0-compatible types
- **AND** compliance is reported as an adapter-level concern, not a core validation failure

#### Scenario: Skip question-specific rules for descriptive items

- **WHEN** a descriptive item is validated
- **THEN** question-specific rules (e.g. double-barrelled question detection, leading question check) are skipped
- **AND** general text quality rules (grammar, clarity) still apply

### Requirement: Question Tagging

The system SHALL automatically suggest metadata tags for questions.

#### Scenario: Suggest tags for single question

- **WHEN** a question is provided
- **THEN** the system suggests relevant tags (e.g., topic, difficulty, question_type)

#### Scenario: Batch tagging for questionnaire

- **WHEN** multiple questions are tagged together
- **THEN** tags are suggested based on section context and question content

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface
for all platform-specific adapters. Each adapter SHALL implement
`import_survey(raw: str) -> Survey`, `export_survey(survey: Survey) -> str`, and
`capabilities() -> set[str]`. The `submit_responses()` method is optional; the
default base implementation SHALL raise `NotImplementedError`. Primary adapters
for MVP: LimeSurvey, Qualtrics. Secondary adapters: SurveyMonkey, QTI 3.0.

Adapters SHALL treat list position as the authoritative order: `import_survey`
SHALL populate `survey.sections` and `section.questions` in the source's display
order, and `export_survey` SHALL derive any platform-specific position or order
value from list index. Adapters SHALL NOT rely on a stored `order` field on the
`Question` or `Section` models.

#### Scenario: Import via adapter

- **WHEN** a questionnaire file is submitted with a specified platform format
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

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, `"responses_export"`. `"create"` indicates the adapter implements `create_survey()`; `"api_create"` additionally indicates that `create_survey()` pushes to a live platform API and returns a platform-assigned ID (as opposed to a file-export fallback). `"responses_export"` indicates the adapter implements `export_responses()` and the resulting bytes are consumable by the platform's first-party response importer (the file format is adapter-defined: LimeSurvey emits TSV in its VV shape; Qualtrics emits CSV).

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, and `"responses_export"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"`, `"api_create"`, or `"responses_export"`

#### Scenario: created_via reflects actual creation path

- **WHEN** `POST /create` succeeds for a LimeSurvey or Qualtrics adapter
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

The system SHALL provide a session-scoped conversational API for iterative
questionnaire authoring. `POST /chat/sessions` SHALL create a new chat session
linked to the authenticated user and return a `session_id`. `GET /chat/sessions`
SHALL list the user's active sessions. `POST /chat/{session_id}` SHALL accept a
user message, run the chat-turn pipeline (including the tool-call loop defined
in the **Chat Turn Tool Surface** requirement), update the draft survey when
the LLM emits a `<survey_update>` block, and return the assistant message and
whether the survey was updated. `GET /chat/{session_id}/survey` SHALL return
the current draft `Survey`. `POST /chat/{session_id}/reset` SHALL clear the
draft survey and tag vocabulary while preserving conversation history and
documents. `DELETE /chat/{session_id}` SHALL end the session and wipe all
session files.

The system prompt used in a chat turn SHALL include a compact summary of the
current draft survey in which each section is anchored by its section ID and
each question is anchored by its question ID. The summary SHALL deliberately
omit question types, answer options, required flags, numeric ranges, metadata,
and descriptions; those fields SHALL be retrievable by the LLM only via the
`get_full_survey` tool defined in the **Chat Turn Tool Surface** requirement.

The persisted conversation history SHALL continue to record only the user
message and the final assistant text for the turn; intermediate tool calls and
tool results SHALL NOT be persisted.

#### Scenario: Start new chat session

- **WHEN** `POST /chat/sessions` is called by an authenticated user
- **THEN** a new session is created with an empty draft survey, default style
  profile, and empty tag vocabulary
- **AND** the session_id is returned

#### Scenario: Iterative question authoring with tool-mediated draft load

- **WHEN** a user message is sent to `POST /chat/{session_id}` and the LLM
  decides to propose changes to the survey
- **THEN** the LLM SHALL call the `get_full_survey` tool to load the
  authoritative draft before emitting a `<survey_update>` block
- **AND** the tool result SHALL be appended to the in-turn conversation as a
  `role: "tool"` message
- **AND** the subsequent LLM response containing `<survey_update>` SHALL be
  parsed and applied to the on-disk draft
- **AND** `survey_updated: true` SHALL be returned

#### Scenario: Pure Q&A turn (no draft change)

- **WHEN** the LLM responds with plain text and no `<survey_update>` block and
  does not call any tool
- **THEN** the chat turn SHALL complete in a single LLM round-trip
- **AND** no tool dispatch SHALL occur
- **AND** the on-disk draft SHALL be unchanged
- **AND** `survey_updated: false` SHALL be returned

#### Scenario: Summary contains IDs as anchors

- **WHEN** the chat-turn system prompt is built from a draft with sections and
  questions
- **THEN** the summary string SHALL contain each section ID at least once
- **AND** SHALL contain each question ID at least once
- **AND** SHALL NOT contain any `answer_options`, `type`, `required`,
  `min_value`, `max_value`, or `metadata` field

#### Scenario: Session isolation

- **WHEN** two users have active chat sessions
- **THEN** each session's draft survey, tag vocabulary, conversation history,
  and style profile are fully isolated

#### Scenario: Session resume

- **WHEN** an authenticated user reconnects within the session TTL window
- **THEN** the session state (draft, vocabulary, history, style profile) is
  fully restored

#### Scenario: Conversation history excludes tool exchanges

- **WHEN** a chat turn dispatches one or more tool calls
- **THEN** the persisted conversation history SHALL record only the user
  message and the final assistant text
- **AND** SHALL NOT contain the tool-call assistant message or the tool result
  message

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

The system SHALL maintain a style profile per Shape session that influences all LLM-generated suggestions, validation feedback, and generated question text. The style profile SHALL include: a `language` field (ISO 639-1, default `"en"`), a `free_text` field for admin-typed style preferences, and a `document_summary` field populated when the admin uploads an institutional style guide document. If no style preferences are provided, the system SHALL apply sensible defaults: English language, neutral formal tone, and rules from the platform's survey design guidelines. The style profile SHALL persist for the lifetime of the session and survive session resume. The admin SHALL be able to update the language or free-text preference at any point during the session.

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

### Requirement: Survey Mutation Tools

The chat-turn pipeline SHALL expose eight core edit tools that together
cover read access and granular mutation of the session draft survey. The
tools are: `get_full_survey`, `init_survey`, `add_section`,
`update_section`, `delete_section`, `add_question`, `update_question`,
`delete_question`. Reordering is handled by the separate `move_section`
and `move_question` tools defined under **Question and Section
Reordering**.

`get_full_survey` SHALL take no parameters and return the full JSON of
the current draft, or a documented sentinel value when no draft exists.

`init_survey` SHALL take a complete `Survey` payload and replace the
draft. It SHALL be used for creating a draft from scratch or for
wholesale restructure; the tool description SHALL discourage its use
for incremental edits.

`add_section` SHALL take a `Section` payload and an optional `after_id`,
inserting the new section after the named section or appending it when
`after_id` is omitted. The supplied section id SHALL be preserved.

`update_section` SHALL take a `section_id` and a partial `SectionPatch`
covering section-level fields (title, description, metadata) only. It
SHALL reject a patch containing a `questions` field.

`delete_section` SHALL take a `section_id` and remove the section and
all of its questions.

`add_question` SHALL take a `section_id`, a `Question` payload, and an
optional `after_id`. The supplied question id SHALL be preserved, which
SHALL allow the LLM to relocate a question across sections by issuing
`delete_question` followed by `add_question` with the same id.

`update_question` SHALL take a `question_id` and a partial
`QuestionPatch`. It SHALL locate the question by id across all sections.

`delete_question` SHALL take a `question_id` and remove it from
wherever it currently lives.

Every mutation tool SHALL return a JSON envelope. On success:
`{"status": "ok", "validation_issues": [...]}` where the issues array
is the output of running the questionnaire validation engine on the
mutated draft. On failure: `{"status": "error", "code": "<code>",
"message": "<actionable hint>"}` where the code is one of
`no_survey_draft`, `section_not_found`, `question_not_found`,
`duplicate_id`, `invalid_patch`. The dispatcher SHALL NOT raise
unhandled exceptions to the LLM under any of these documented error
conditions.

Mutation tools SHALL share a single underlying implementation with the
HTTP mutation endpoints described in **Survey Mutation HTTP Endpoints**;
both surfaces SHALL produce identical state changes and identical
validation feedback for the same logical mutation.

#### Scenario: Successful question update returns validation issues

- **WHEN** the LLM calls `update_question` with a valid `question_id`
  and a patch that succeeds
- **THEN** the draft on disk SHALL reflect the patched fields
- **AND** the tool response SHALL be `{"status": "ok",
  "validation_issues": [...]}` with the issues array reflecting the
  current state of the draft after the change

#### Scenario: Update on unknown question returns structured error

- **WHEN** the LLM calls `update_question` with a `question_id` that
  does not exist in the draft
- **THEN** the tool response SHALL be `{"status": "error", "code":
  "question_not_found", "message": "..."}` where the message includes
  a hint to call `get_full_survey`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Add with duplicate id rejected

- **WHEN** the LLM calls `add_section` (or `add_question`) with an id
  that already exists in the draft
- **THEN** the tool response SHALL be `{"status": "error", "code":
  "duplicate_id", "message": "..."}`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Mutation before init_survey returns no_survey_draft

- **WHEN** the LLM calls any mutation tool other than `init_survey` or
  `get_full_survey` when no draft yet exists for the session
- **THEN** the tool response SHALL be `{"status": "error", "code":
  "no_survey_draft", "message": "Call init_survey first."}`
- **AND** no draft SHALL be created as a side effect

#### Scenario: Question id preserved across move

- **WHEN** the LLM calls `delete_question` for a question id followed
  by `add_question` with the same id and a different `section_id`
- **THEN** the question SHALL appear in the new section with its
  original id

#### Scenario: Update_section rejects questions field

- **WHEN** the LLM calls `update_section` with a patch body containing
  a `questions` field
- **THEN** the tool response SHALL be `{"status": "error", "code":
  "invalid_patch", "message": "..."}` referencing the disallowed field
- **AND** the on-disk draft SHALL be unchanged

### Requirement: Survey Mutation HTTP Endpoints

The system SHALL expose REST endpoints that mirror the Survey Mutation
Tools, sharing the same underlying mutation implementation. The
endpoints SHALL be:

- `POST /chat/{session_id}/survey/sections` — body `{section, after_id?}`
- `PATCH /chat/{session_id}/survey/sections/{section_id}` — body
  `SectionPatch`
- `DELETE /chat/{session_id}/survey/sections/{section_id}`
- `POST /chat/{session_id}/survey/sections/{section_id}/questions` —
  body `{question, after_id?}`
- `PATCH /chat/{session_id}/survey/questions/{question_id}` — body
  `QuestionPatch`
- `DELETE /chat/{session_id}/survey/questions/{question_id}`

Every mutation endpoint SHALL be authenticated and SHALL verify that
the caller owns the session, returning `401` when unauthenticated and
`403` when ownership is missing. Every mutation endpoint SHALL return
`200` with a body of shape `{"status": "saved", "validation_issues":
[...]}` on success. Mutation errors SHALL be mapped to HTTP status
codes as follows: `section_not_found` and `question_not_found` to
`404`; `duplicate_id` to `409`; `no_survey_draft` and `invalid_patch`
to `400`. The existing `PUT /chat/{session_id}/survey` endpoint SHALL
remain available and SHALL retain its current behaviour (full-survey
replace from form-editor flows).

#### Scenario: Add section returns saved with validation issues

- **WHEN** an authenticated owner POSTs `{section: {...}}` to
  `/chat/{session_id}/survey/sections`
- **THEN** the response status SHALL be `200`
- **AND** the response body SHALL contain `"status": "saved"` and a
  `validation_issues` array reflecting the post-mutation state
- **AND** the on-disk draft SHALL include the new section

#### Scenario: Patch nonexistent question returns 404

- **WHEN** an authenticated owner PATCHes
  `/chat/{session_id}/survey/questions/unknown_id`
- **THEN** the response status SHALL be `404`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Add with duplicate id returns 409

- **WHEN** an authenticated owner POSTs a section whose id already
  exists in the draft
- **THEN** the response status SHALL be `409`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Unauthenticated mutation returns 401

- **WHEN** any mutation endpoint is called without a valid bearer token
- **THEN** the response status SHALL be `401`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Foreign-session mutation returns 403

- **WHEN** an authenticated user calls a mutation endpoint for a session
  owned by a different user
- **THEN** the response status SHALL be `403`
- **AND** the on-disk draft SHALL be unchanged

#### Scenario: Shared implementation with tools

- **WHEN** the same logical mutation is applied via the LLM tool path
  and via the HTTP endpoint path on equivalent inputs
- **THEN** the resulting draft state SHALL be identical
- **AND** the `validation_issues` returned SHALL be identical

### Requirement: Section Size Methodological Warnings

The questionnaire validation engine SHALL emit a `section_dense`
warning for any section containing more than 30 questions, and a
`section_overlong` warning for any section containing more than 50
questions. The two codes SHALL be mutually exclusive (a section with
60 questions emits only `section_overlong`). The warnings SHALL flow
through the same `validation_issues` array surfaced by the mutation
tools and HTTP endpoints, allowing both the LLM and HTTP callers to
react to them. No hard cap SHALL be enforced; legitimate psychometric
instruments may exceed both thresholds.

#### Scenario: Dense section warning at 31 questions

- **WHEN** a section contains 31 questions
- **THEN** the validation issues SHALL include an issue with code
  `section_dense` and severity `warning`
- **AND** the message SHALL identify the section by title and report
  the count

#### Scenario: Overlong section warning at 51 questions

- **WHEN** a section contains 51 questions
- **THEN** the validation issues SHALL include an issue with code
  `section_overlong` and severity `warning`
- **AND** SHALL NOT include `section_dense` for the same section

#### Scenario: No warning at the threshold

- **WHEN** a section contains exactly 30 questions
- **THEN** the validation issues SHALL include neither `section_dense`
  nor `section_overlong` for that section

### Requirement: Question and Section Reordering

The system SHALL provide operations to change the position of an existing
question or section without recreating it, exposed both as LLM tools
(`move_question`, `move_section`) and as HTTP endpoints
(`PATCH /chat/{session_id}/survey/questions/{question_id}/position` and
`PATCH /chat/{session_id}/survey/sections/{section_id}/position`).
`move_question` SHALL accept an optional `after_id` (place the question
immediately after that question; omitted = move to the start of the target
section) and an optional `section_id` (move the question into a different
section, preserving its id). `move_section` SHALL accept an optional `after_id`.
These operations SHALL change list position only and SHALL NOT alter any other
field.

#### Scenario: Reorder a question within its section

- **WHEN** `move_question` is called with an `after_id` in the same section
- **THEN** the question is positioned immediately after that question
- **AND** its id and all other fields are unchanged

#### Scenario: Move a question to the start of a section

- **WHEN** `move_question` is called with no `after_id`
- **THEN** the question is placed first in the target section

#### Scenario: Move a question to another section

- **WHEN** `move_question` is called with a `section_id` different from the
  question's current section
- **THEN** the question is removed from its current section and inserted into the
  target section, preserving its id

#### Scenario: Reorder a section

- **WHEN** `move_section` is called with an `after_id`
- **THEN** the section is positioned immediately after that section

#### Scenario: Move references an unknown id

- **WHEN** a move operation references a question or section id that does not
  exist
- **THEN** a not-found error (`question_not_found` or `section_not_found`) is
  returned and the draft is unchanged

### Requirement: Chat Turn Tool Surface

The chat-turn pipeline SHALL expose a single LLM tool named `get_full_survey`
that returns the full JSON of the current session draft survey, read from disk
at call time. The tool SHALL take no parameters; the session SHALL be implicit
in the chat-turn execution context. The tool result SHALL be a JSON string
representing either the full `Survey` object or a sentinel value when no draft
exists.

`execute_chat_turn` SHALL implement a tool-call loop with a bounded maximum of
3 iterations. On each iteration the LLM SHALL be called with the conversation
messages and the `[get_full_survey]` tool definition. If the response message
contains tool calls, the loop SHALL dispatch each call, append the assistant
tool-call message and each tool result message to the in-turn messages array,
and continue. If the response message contains no tool calls, the loop SHALL
exit and the `<survey_update>` parsing path SHALL run on the response content.
If the loop reaches the iteration cap, the last assistant message SHALL be
treated as the final response, a warning SHALL be logged with session ID and
iteration count, and any remaining tool calls SHALL be ignored.

The system prompt SHALL contain a soft directive instructing the LLM to call
`get_full_survey` before emitting any `<survey_update>` block. The directive
SHALL NOT be enforced server-side: an `<survey_update>` arriving without a
prior tool call within the same turn SHALL still be applied, but the server
SHALL log a warning containing the session ID and a non-compliance marker so
that operators can monitor adoption.

Each successful `get_full_survey` invocation SHALL emit a structured log
entry containing the session ID and an in-turn iteration counter at INFO
level. The audit ledger (`m_shared/utils/audit.py`) SHALL NOT be extended for
this surface; it is administrator-side observability, not respondent-facing
transparency.

#### Scenario: Tool returns current draft

- **WHEN** the LLM calls `get_full_survey` during a chat turn for a session
  with an existing draft
- **THEN** the dispatcher SHALL read `draft_survey.json` from disk and return
  its JSON content to the LLM
- **AND** the tool result SHALL be appended to the in-turn conversation as a
  `role: "tool"` message tagged with the call ID

#### Scenario: Tool called with no existing draft

- **WHEN** the LLM calls `get_full_survey` and the session has no draft on
  disk
- **THEN** the dispatcher SHALL return a documented sentinel JSON value
- **AND** the LLM SHALL receive that value as the tool result without error

#### Scenario: Loop exits cleanly on text-only response

- **WHEN** the LLM responds without any tool calls
- **THEN** the loop SHALL exit after the single iteration
- **AND** the response content SHALL be parsed for `<survey_update>`

#### Scenario: Loop caps at the maximum iteration count

- **WHEN** the LLM emits tool calls on three consecutive iterations
- **THEN** the loop SHALL stop after the third iteration
- **AND** a warning SHALL be logged identifying the session and iteration
  count
- **AND** the third response SHALL be treated as final

#### Scenario: Update applied without prior tool call logs a warning

- **WHEN** the LLM emits a `<survey_update>` on its first response without
  calling `get_full_survey`
- **THEN** the update SHALL still be applied to the draft (soft enforcement)
- **AND** a warning SHALL be logged identifying the session and indicating
  non-compliance with the prompt directive

#### Scenario: Tool invocation logged at INFO level

- **WHEN** a `get_full_survey` call dispatches successfully
- **THEN** a structured INFO log entry SHALL be emitted including the session
  ID and the in-turn iteration counter

### Requirement: Response File Export via Adapter

Adapters that support file-based response export SHALL implement
`export_responses(survey: Survey, responses: list[Response]) -> ResponseExport`,
which returns a `ResponseExport` named tuple of `(content: bytes,
media_type: str, filename_suffix: str)`. The returned bytes SHALL be
importable into the originating platform's admin UI without further
transformation. The exact file format is adapter-defined — different
platforms accept different formats from their admin importers — and the
adapter declares it via the returned `media_type` and `filename_suffix`.

Adapters that do not support this path SHALL leave the method as the base
`NotImplementedError`. This capability is independent of `submit_responses`:
an adapter MAY implement either, both, or neither.

The export path is a deliberately offline fallback for environments where
the platform's API is not available. It is never substituted automatically
for an API submission; the caller chooses the path explicitly.

#### Scenario: LimeSurvey VV export

- **WHEN** `export_responses()` is called on the LimeSurvey adapter with a
  parsed survey and a list of responses
- **THEN** the returned bytes are TAB-separated (LS's "VV" — Vertical
  Verification — format, distinct from CSV; the filename ends in
  `_vv.csv` to mirror LS's own `vvexport_{sid}.csv` naming style)
- **AND** the file begins with TWO header rows: row 1 is human display
  labels, row 2 is the column codes the importer maps —
  `id`, `token`, `submitdate`, `lastpage`, `startlanguage`, `seed`,
  `startdate`, `datestamp` followed by one column per top-level question
  keyed by its user-defined code (`ls_qcode`) and one column per `M`/`P`
  sub-question keyed `{qcode}_{sub_qcode}` (UNDERSCORE separator)
- **AND** data rows encode single-choice answers as the option code,
  multi-choice selected sub-questions as `Y` (unselected as the literal
  `{question_not_shown}` marker), and text/numeric answers verbatim
- **AND** `media_type` is `text/tab-separated-values; charset=utf-8` and
  `filename_suffix` is `_vv.csv` (the suffix INCLUDES its leading
  connector — underscore — to mirror LS's own `vvexport_{sid}.csv` style)
- **AND** the file is importable by the LimeSurvey admin "Import a VV
  response data file" feature without further transformation

#### Scenario: Qualtrics CSV export

- **WHEN** `export_responses()` is called on the Qualtrics adapter with
  a parsed survey and a list of responses
- **THEN** the returned bytes are a UTF-8 CSV (with BOM) with three header
  rows: row 1 the Qualtrics column IDs (`ResponseId`, `StartDate`,
  `EndDate`, …, `QID<n>`, …), row 2 the human-readable question text, and
  row 3 the Qualtrics import-metadata JSON object per column
- **AND** the data rows starting at row 4 encode one response per row in
  the column order established by row 1
- **AND** `media_type` is `text/csv; charset=utf-8` and `filename_suffix`
  is `.csv`
- **AND** the CSV is importable by the Qualtrics "Import Responses" feature
  without further transformation

#### Scenario: Adapter without response export

- **WHEN** `export_responses()` is called on an adapter that does not
  implement it (QTI, SurveyMonkey)
- **THEN** `NotImplementedError` is raised with a message identifying the
  adapter and naming the `"responses_export"` capability the caller should
  check before invoking

#### Scenario: Empty response list

- **WHEN** `export_responses()` is called with an empty response list
- **THEN** the returned bytes contain only the platform's header row(s) —
  no data rows
- **AND** the file is still well-formed and importable (the platform's
  importer treats it as a zero-row import)

## Notes

- MVP scope: Support five core question types (multiple_choice, single_choice, open_ended, ranking, slider)
- No conditional branching logic in MVP
- LLM used for suggestions and validation; deterministic rule-based validation for compliance checks
- Located in `shape_api/suggestion_engine.py`, `validation_engine.py`, `tagging_engine.py`
- Integrated with data-models capability for Survey/Question representation
- Adapter `create` capability: platforms with a write API (LimeSurvey, Qualtrics) SHALL support `create_survey(survey: Survey) -> str` returning the platform-assigned survey ID; platforms without a write API (SurveyMonkey, QTI) SHALL respond to `create` by returning an exported file payload (i.e., a file download fallback)
