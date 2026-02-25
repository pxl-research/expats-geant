## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Consistent LLM Prompt Format

The system SHALL use the same JSON response format for both single-question and batch suggestion prompts.

#### Scenario: Single and batch prompts use identical format

- **WHEN** either `POST /suggest` or `POST /suggest/batch` generates an LLM prompt
- **THEN** both instruct the LLM to respond with the same JSON schema: `{"answer": "...", "selected": "...", "reasoning": "..."}`

#### Scenario: Choice selection omitted for open-ended questions

- **WHEN** a question is of type `open_ended`
- **THEN** the `selected` field is omitted from the prompt and returned as `null`
