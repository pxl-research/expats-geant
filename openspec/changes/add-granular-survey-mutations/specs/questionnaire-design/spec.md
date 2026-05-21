## MODIFIED Requirements

### Requirement: Conversational Session API

The system SHALL provide a session-scoped conversational API for iterative
questionnaire authoring. `POST /chat/sessions` SHALL create a new chat
session linked to the authenticated user and return a `session_id`.
`GET /chat/sessions` SHALL list the user's active sessions.
`POST /chat/{session_id}` SHALL accept a user message, run a chat-turn
tool-call loop in which the LLM applies structural changes to the draft
survey by invoking the **Survey Mutation Tools**, and return the
assistant message and a `survey_updated` boolean that is `true` when at
least one mutation tool returned a successful status during the turn.
`GET /chat/{session_id}/survey` SHALL return the current draft `Survey`.
`POST /chat/{session_id}/reset` SHALL clear the draft survey and tag
vocabulary while preserving conversation history and documents.
`DELETE /chat/{session_id}` SHALL end the session and wipe all session
files.

The chat-turn tool-call loop SHALL be bounded by a maximum of **25**
iterations. On each iteration the LLM SHALL be called with the
conversation messages and the full mutation tool set. If the response
contains tool calls, the loop SHALL dispatch each one through the
mutation layer, append the structured tool result message to the
in-turn conversation, and continue. If the response contains no tool
calls, the loop SHALL exit and the response content SHALL be returned
as the final assistant message. If the loop reaches the iteration cap,
the last assistant message SHALL be treated as the final response and
a warning SHALL be logged with the session ID and iteration count.

The chat-turn pipeline SHALL NOT parse the assistant content for
`<survey_update>` tags; structural changes SHALL flow only through
mutation tool calls. When the LLM's final response is truncated by the
provider (`finish_reason == "length"`) and no mutation tool succeeded,
the chat turn SHALL return a clean user-facing message instructing the
user to split the change into smaller steps, rather than leaking
partial JSON into the chat.

The persisted conversation history SHALL continue to record only the
user message and the final assistant text for the turn; intermediate
tool calls and tool results SHALL NOT be persisted.

#### Scenario: Start new chat session

- **WHEN** `POST /chat/sessions` is called by an authenticated user
- **THEN** a new session is created with an empty draft survey, default
  style profile, and empty tag vocabulary
- **AND** the session_id is returned

#### Scenario: Edit a question via mutation tool

- **WHEN** a user asks during a chat turn to reword an existing question
- **THEN** the LLM SHALL call `get_full_survey` to load the current
  draft
- **AND** SHALL then call `update_question` with the target
  `question_id` and only the `text` field in the patch
- **AND** the on-disk draft SHALL reflect the new wording after the
  turn
- **AND** the chat turn response SHALL carry `survey_updated: true`

#### Scenario: Multi-tool edit turn

- **WHEN** the LLM emits multiple mutation tool calls within a single
  iteration (for example, `add_section` plus two `add_question` calls
  in parallel)
- **THEN** each tool call SHALL be dispatched in order
- **AND** each SHALL be persisted independently
- **AND** the chat turn response SHALL carry `survey_updated: true`

#### Scenario: Pure Q&A turn

- **WHEN** the LLM responds with plain text and invokes no tools
- **THEN** the loop SHALL exit after a single iteration
- **AND** the on-disk draft SHALL be unchanged
- **AND** the chat turn response SHALL carry `survey_updated: false`

#### Scenario: Truncated init_survey payload

- **WHEN** the LLM calls `init_survey` with a payload that is truncated
  by the provider (`finish_reason == "length"`) and no other mutation
  tool succeeded during the turn
- **THEN** the chat turn response SHALL contain a clean user-facing
  message instructing the user to split the change into smaller steps
- **AND** the chat turn SHALL NOT leak partial JSON into the chat
- **AND** the chat turn response SHALL carry `survey_updated: false`

#### Scenario: Loop caps at the maximum iteration count

- **WHEN** the LLM continues emitting tool calls past the 25th
  iteration
- **THEN** the loop SHALL exit after the 25th iteration
- **AND** a warning SHALL be logged identifying the session and the
  iteration count
- **AND** the chat turn response SHALL fall back to a user-facing
  message asking the user to rephrase or split the change

#### Scenario: Session isolation

- **WHEN** two users have active chat sessions
- **THEN** each session's draft survey, tag vocabulary, conversation
  history, and style profile are fully isolated

#### Scenario: Session resume

- **WHEN** an authenticated user reconnects within the session TTL
  window
- **THEN** the session state (draft, vocabulary, history, style
  profile) is fully restored

#### Scenario: Conversation history excludes tool exchanges

- **WHEN** a chat turn dispatches one or more mutation tool calls
- **THEN** the persisted conversation history SHALL record only the
  user message and the final assistant text
- **AND** SHALL NOT contain any tool-call assistant message or any tool
  result message

## ADDED Requirements

### Requirement: Survey Mutation Tools

The chat-turn pipeline SHALL expose eight LLM tools that together cover
read access and granular mutation of the session draft survey. The
tools are: `get_full_survey`, `init_survey`, `add_section`,
`update_section`, `delete_section`, `add_question`, `update_question`,
`delete_question`.

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
covering section-level fields (title, description, order, metadata)
only. It SHALL reject a patch containing a `questions` field.

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
