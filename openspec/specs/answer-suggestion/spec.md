# Capability: Answer Suggestion (Cue)

## Purpose

RAG-based answer suggestion engine that retrieves relevant document passages, generates draft answers, and provides citations with source transparency.
## Requirements
### Requirement: Semantic Retrieval

The system SHALL retrieve relevant document chunks via semantic search.

When query distillation is enabled, the system SHALL distill survey questions into concise search queries using the configured LLM before performing vector search. The distilled query replaces the raw question text for retrieval only; the original question text is preserved for answer generation and audit logging.

Distillation SHALL be batched per survey section, with a configurable upper bound on batch size. Sections exceeding the batch size limit SHALL be split into sub-batches.

The distillation prompt SHALL include: the question text, question type, answer choices (for choice-type questions), section title, and document filenames from the session.

If distillation fails (LLM error, timeout, or unparseable output), the system SHALL fall back to using the original question text for retrieval without raising an error.

Query distillation SHALL be enabled by default and configurable via environment variable.

#### Scenario: Search documents for question context

- **WHEN** a question and optional context are provided
- **THEN** the system retrieves top-k document chunks ranked by semantic similarity

#### Scenario: Return metadata with results

- **WHEN** documents are retrieved
- **THEN** results include source, position/percentage, timestamp, and other citation metadata

#### Scenario: Distilled query used for retrieval

- **WHEN** query distillation is enabled and a batch of questions is submitted
- **THEN** each question is distilled into a concise search query before vector search
- **AND** the distilled query is used for ChromaDB retrieval
- **AND** the original question text is used for answer generation

#### Scenario: Distillation includes answer choices

- **WHEN** a choice-type question (single_choice or multiple_choice) is distilled
- **THEN** the choice labels are included in the distillation prompt as additional context

#### Scenario: Distillation batched per section

- **WHEN** a section contains multiple questions
- **THEN** all questions in the section are distilled in a single LLM call (up to the configured batch size limit)
- **AND** sections exceeding the batch size limit are split into sub-batches

#### Scenario: Graceful fallback on distillation failure

- **WHEN** the distillation LLM call fails or returns unparseable output
- **THEN** the system uses the original question text for retrieval
- **AND** no error is raised to the caller

#### Scenario: Distillation disabled via configuration

- **WHEN** query distillation is disabled via environment variable
- **THEN** the system uses the original question text for retrieval (existing behaviour)

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

The system SHALL use the same JSON response format for batch and streaming suggestion
prompts.

#### Scenario: Batch and streaming prompts use identical format

- **WHEN** either `POST /suggest/batch` or `POST /suggest/stream` generates an LLM prompt
- **THEN** both instruct the LLM to respond with the same JSON schema:
  `{"answer": "...", "selected": "...", "reasoning": "..."}`

#### Scenario: Choice selection omitted for open-ended questions

- **WHEN** a question is of type `open_ended`
- **THEN** the `selected` field is omitted from the LLM prompt; because the LLM does not include it in its response, the parser treats the missing field as `null`

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

### Requirement: Review State API

The system SHALL provide API endpoints for persisting and retrieving per-question review
state within a Cue session. Review state tracks the respondent's decision for each
suggestion: accepted, dismissed, edited, or pending.

`PUT /review-state/{question_id}` SHALL save the review state for a single question.
The request body SHALL include `state` (one of `accepted`, `dismissed`, `edited`) and
optionally `value` (the respondent's answer text), `selected_id` (matched choice ID for
single-choice questions), or `selected_ids` (matched choice IDs for multiple-choice
questions).

`GET /review-state` SHALL return the full review state map for the session as a JSON
object keyed by question ID.

Review state SHALL be stored as `review_state.json` in the session directory and
deleted automatically when the session is deleted.

#### Scenario: Save accepted state

- **WHEN** `PUT /review-state/q_1` is called with `{"state": "accepted", "value": "36 months"}`
- **THEN** the review state for question `q_1` is persisted
- **AND** subsequent `GET /review-state` includes `q_1` with state `accepted`

#### Scenario: Save dismissed state

- **WHEN** `PUT /review-state/q_2` is called with `{"state": "dismissed"}`
- **THEN** the review state for question `q_2` is persisted as dismissed

#### Scenario: Save edited state with choice selection

- **WHEN** `PUT /review-state/q_3` is called with `{"state": "edited", "selected_ids": ["opt_a", "opt_c"]}`
- **THEN** the review state for question `q_3` is persisted with the edited selections

#### Scenario: Load full review state

- **WHEN** `GET /review-state` is called for a session with saved review decisions
- **THEN** a JSON object is returned mapping each reviewed question ID to its state

#### Scenario: Load empty review state

- **WHEN** `GET /review-state` is called for a session with no saved review decisions
- **THEN** an empty JSON object is returned

#### Scenario: State overwritten on re-review

- **WHEN** a question's review state is saved multiple times (e.g. accepted then edited)
- **THEN** only the latest state is retained

## Notes

- MVP scope: Basic RAG retrieval + LLM generation + citations (no re-ranking, no answer ranking/filtering)
- Session isolation: Ephemeral per-session ChromaDB instance
- TTL-based cleanup integrated with vector-db capability
- Located in `cue_api/rag_pipeline.py`
- Depends on: document-ingestion, vector-db, llm-integration, data-models
