# Capability: Answer Suggestion (M-Autofill)

## Purpose

RAG-based answer suggestion engine that retrieves relevant document passages, generates draft answers, and provides citations with source transparency.
## Requirements
### Requirement: Semantic Retrieval

The system SHALL retrieve relevant document chunks via semantic search.

#### Scenario: Search documents for question context

- **WHEN** a question and optional context are provided
- **THEN** the system retrieves top-k document chunks ranked by semantic similarity

#### Scenario: Return metadata with results

- **WHEN** documents are retrieved
- **THEN** results include source, position/percentage, timestamp, and other citation metadata

### Requirement: Answer Generation

The system SHALL generate concise draft answers based on retrieved passages.

#### Scenario: Generate answer from retrieved passages

- **WHEN** retrieval returns relevant chunks
- **THEN** the system generates a short, coherent answer informed by those passages

#### Scenario: LLM generation with temperature control

- **WHEN** answer generation is invoked
- **THEN** it uses configured temperature for consistent, slightly deterministic output

#### Scenario: LLM response parsed as JSON

- **WHEN** the LLM returns a structured response
- **THEN** the system parses it as JSON to extract `answer`, `selected`, and `reasoning` fields
- **AND** if the response is wrapped in markdown code fences, they are stripped before parsing

#### Scenario: Graceful fallback on malformed LLM response

- **WHEN** the LLM response cannot be parsed as valid JSON
- **THEN** the full response text is used as the `answer`
- **AND** `selected` and `reasoning` are set to `null`
- **AND** the parse failure is logged as a warning

### Requirement: Citation System

The system SHALL provide precise citations showing which document passages informed the answer.

#### Scenario: Citations include source metadata

- **WHEN** an answer is suggested
- **THEN** citations include source name, position/percentage, timestamp, and optional text highlights

#### Scenario: Highlight relevant passage

- **WHEN** a citation is created
- **THEN** it includes the exact text excerpt from the source for user verification

### Requirement: Session Isolation

The system SHALL maintain document and suggestion state per user session with automatic cleanup.

#### Scenario: Each session has independent documents

- **WHEN** a user uploads documents to a session
- **THEN** those documents are only available within that session

#### Scenario: Session TTL ensures data cleanup

- **WHEN** a session expires
- **THEN** all associated documents, vectors, and suggestions are deleted

### Requirement: User-Provided Answer Context

The system SHALL accept and preserve user-edited answers during a session.

#### Scenario: User modifies suggested answer

- **WHEN** a user edits a suggestion before submission
- **THEN** the edited answer is stored (as optional field for audit purposes)

### Requirement: Consistent LLM Prompt Format

The system SHALL use the same JSON response format for single-question, batch, and
streaming suggestion prompts.

#### Scenario: Single, batch, and streaming prompts use identical format

- **WHEN** any of `POST /suggest`, `POST /suggest/batch`, or `POST /suggest/stream` generates an LLM prompt
- **THEN** all instruct the LLM to respond with the same JSON schema: `{"answer": "...", "selected": "...", "reasoning": "..."}`

#### Scenario: Choice selection omitted for open-ended questions

- **WHEN** a question is of type `open_ended`
- **THEN** the `selected` field is omitted from the prompt and returned as `null`

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

## Notes

- MVP scope: Basic RAG retrieval + LLM generation + citations (no re-ranking, no answer ranking/filtering)
- Session isolation: Ephemeral per-session ChromaDB instance
- TTL-based cleanup integrated with vector-db capability
- Located in `cue_api/rag_pipeline.py`
- Depends on: document-ingestion, vector-db, llm-integration, data-models
