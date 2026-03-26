## ADDED Requirements

### Requirement: Streaming Suggestion Delivery

The system SHALL provide a `POST /suggest/stream` endpoint that emits suggestions as a
Server-Sent Events (SSE) stream, delivering each suggestion immediately after its LLM
call completes rather than waiting for all questions to be processed.

The endpoint SHALL accept the same `BatchSuggestRequest` body as `POST /suggest/batch`.
Each event SHALL carry the same fields as an `ItemSuggestion` response object.
A final `event: done` event SHALL be emitted when all items have been processed.

The endpoint SHALL NOT block the FastAPI event loop during LLM generation; LLM calls
SHALL be offloaded to a thread pool via `asyncio.run_in_executor`.

#### Scenario: Suggestions delivered progressively

- **WHEN** a client connects to `POST /suggest/stream` with a valid session and item list
- **THEN** the server emits one `event: suggestion` SSE event per question in processing order
- **AND** each event is emitted as soon as that question's LLM call completes
- **AND** a final `event: done` event is emitted after all items are processed

#### Scenario: Stream survives individual item failure

- **WHEN** the LLM call for one question raises an exception
- **THEN** the stream emits a degraded suggestion for that item (matching the batch fallback behaviour)
- **AND** processing continues for remaining questions
- **AND** the stream is not terminated by the failure

#### Scenario: Event loop not blocked during generation

- **WHEN** a streaming suggestion request is in progress
- **THEN** other API endpoints (e.g. `/health`, `/surveys/{id}`) remain responsive
- **AND** the LLM call runs in a thread pool, not on the async event loop

## MODIFIED Requirements

### Requirement: Consistent LLM Prompt Format

The system SHALL use the same JSON response format for single-question, batch, and
streaming suggestion prompts.

#### Scenario: Single, batch, and streaming prompts use identical format

- **WHEN** any of `POST /suggest`, `POST /suggest/batch`, or `POST /suggest/stream` generates an LLM prompt
- **THEN** all instruct the LLM to respond with the same JSON schema: `{"answer": "...", "selected": "...", "reasoning": "..."}`

#### Scenario: Choice selection omitted for open-ended questions

- **WHEN** a question is of type `open_ended`
- **THEN** the `selected` field is omitted from the prompt and returned as `null`
