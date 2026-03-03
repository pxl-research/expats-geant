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

The system SHALL use the same JSON response format for both single-question and batch suggestion prompts.

#### Scenario: Single and batch prompts use identical format

- **WHEN** either `POST /suggest` or `POST /suggest/batch` generates an LLM prompt
- **THEN** both instruct the LLM to respond with the same JSON schema: `{"answer": "...", "selected": "...", "reasoning": "..."}`

#### Scenario: Choice selection omitted for open-ended questions

- **WHEN** a question is of type `open_ended`
- **THEN** the `selected` field is omitted from the prompt and returned as `null`

## Notes

- MVP scope: Basic RAG retrieval + LLM generation + citations (no re-ranking, no answer ranking/filtering)
- Session isolation: Ephemeral per-session ChromaDB instance
- TTL-based cleanup integrated with vector-db capability
- Located in `m_autofill/rag_pipeline.py`
- Depends on: document-ingestion, vector-db, llm-integration, data-models
