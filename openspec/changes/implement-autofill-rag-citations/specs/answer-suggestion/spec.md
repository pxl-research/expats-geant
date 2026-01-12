# Capability: Answer Suggestion (M-Autofill) — Phase 3.1 Delta

## MODIFIED Requirements

### Requirement: Semantic Retrieval

The system SHALL retrieve relevant document chunks via semantic search in response to a user's question.

#### Scenario: Search documents for question context

- **WHEN** a question and optional context are provided
- **THEN** the system queries ChromaDB for top-k (configurable, default 5) document chunks ranked by semantic similarity
- **AND** returns results with metadata preserved (source filename, chunk index, position/percentage, upload timestamp)

#### Scenario: Return metadata with results

- **WHEN** documents are retrieved
- **THEN** each result includes:
  - Source document name (filename)
  - Chunk index (position in source)
  - Position/percentage (where in document)
  - Upload timestamp (when added to session)
  - Full chunk text (for context)

#### Scenario: Handle empty or no-result queries

- **WHEN** no chunks match the query (similarity below threshold)
- **THEN** the system returns empty result with clear message
- **AND** logs the query attempt for audit

### Requirement: Answer Generation

The system SHALL generate concise draft answers based on retrieved passages using the LLM client.

#### Scenario: Generate answer from retrieved passages

- **WHEN** retrieval returns ≥1 relevant chunks
- **THEN** the system constructs a prompt with the question and retrieved passages
- **AND** calls the LLM client to generate a short, coherent answer

#### Scenario: LLM generation with temperature control

- **WHEN** answer generation is invoked
- **THEN** it uses configured temperature (0.3–0.5 for deterministic output)
- **AND** ensures output is concise (max 500 tokens, configurable)

#### Scenario: Handle LLM failures gracefully

- **WHEN** LLM generation fails (timeout, API error, rate limit)
- **THEN** the system returns a clear error message
- **AND** does not return a partial or hallucinated answer

### Requirement: Citation System

The system SHALL provide precise citations showing which document passages informed the answer.

#### Scenario: Citations include source metadata

- **WHEN** an answer is suggested
- **THEN** each citation includes:
  - Source document name (filename)
  - Position/percentage in source (e.g., "45% through document")
  - Upload timestamp (when document was added)
  - Exact text excerpt from the source (50–200 characters for context)

#### Scenario: Highlight relevant passage

- **WHEN** a citation is created
- **THEN** the exact text excerpt is extracted from the source chunk
- **AND** the excerpt clearly shows the context that informed the answer

#### Scenario: Multiple sources in a single answer

- **WHEN** the answer draws from multiple document chunks
- **THEN** all relevant citations are included
- **AND** each citation is labeled (e.g., "[1]", "[2]") for reference in the answer

### Requirement: Session Isolation

The system SHALL maintain document and suggestion state per user session with automatic cleanup.

#### Scenario: Each session has independent documents

- **WHEN** a user uploads documents to a session
- **THEN** those documents are indexed in a session-scoped ChromaDB instance
- **AND** retrieval queries only search within that session's documents

#### Scenario: Suggestions only available within session

- **WHEN** a suggestion is generated
- **THEN** it is tied to the session_id
- **AND** cannot be accessed from a different session

### Requirement: Answer Generation Input Validation

The system SHALL validate answer generation inputs to prevent malformed or injection attacks.

#### Scenario: Validate question format

- **WHEN** an answer generation request is received
- **THEN** the question is validated (non-empty, reasonable length, no injection patterns)
- **AND** a ValidationError is raised for invalid input

#### Scenario: Validate session context

- **WHEN** an answer generation request includes a session_id
- **THEN** the system verifies the session exists and is valid
- **AND** returns a clear error if session not found or expired
