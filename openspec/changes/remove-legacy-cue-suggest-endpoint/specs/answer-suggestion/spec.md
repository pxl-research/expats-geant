## MODIFIED Requirements

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
