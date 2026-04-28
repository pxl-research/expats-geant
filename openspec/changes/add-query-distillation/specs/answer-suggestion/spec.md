## MODIFIED Requirements

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
