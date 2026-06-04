## MODIFIED Requirements

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

## ADDED Requirements

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
