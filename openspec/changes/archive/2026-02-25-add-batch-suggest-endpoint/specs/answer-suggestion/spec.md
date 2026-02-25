## ADDED Requirements

### Requirement: Batch Answer Suggestion

The system SHALL accept multiple questionnaire items in a single request and return a structured suggestion for each item.

#### Scenario: Batch request with multiple items

- **WHEN** a `POST /suggest/batch` request is made with a valid assessment payload containing multiple items
- **THEN** the system returns one suggestion object per item, each with an answer, optional choice selection, optional remark, and citations

#### Scenario: Empty citations when no evidence found

- **WHEN** no relevant document chunks are found for a given item
- **THEN** the suggestion includes an empty `citations` array and a `remark` explaining the absence of evidence

### Requirement: Section Context Injection

The system SHALL use sibling question prompts within the same section as additional context when generating suggestions.

#### Scenario: Related questions benefit from shared context

- **WHEN** items are grouped in a named section
- **THEN** the LLM receives the section title and all sibling item prompts as part of the generation context for each item in that section

#### Scenario: Flat item list treated as single implicit section

- **WHEN** a batch request provides a top-level `items` array instead of `sections`
- **THEN** all items are treated as belonging to one implicit section with no title, and sibling context is applied across all items

### Requirement: Structured Suggestion Response

The system SHALL return a structured suggestion response per item containing a human-readable answer, machine-parseable choice selection for choice-type questions, an optional LLM remark, and source citations.

#### Scenario: Open-ended item response

- **WHEN** an item of type `open_ended` is processed
- **THEN** the response contains `suggestion` (string) and `citations`, with no `selected_id` field

#### Scenario: Single-choice item response with confident selection

- **WHEN** an item of type `single_choice` is processed and the LLM can confidently map to a choice
- **THEN** the response contains `suggestion`, `selected_id` matching one of the input `choices[].id` values, and `citations`

#### Scenario: Single-choice item response with uncertain selection

- **WHEN** an item of type `single_choice` is processed and the LLM cannot confidently select a choice
- **THEN** `selected_id` is `null` and `reasoning` explains the uncertainty

#### Scenario: Multiple-choice item response

- **WHEN** an item of type `multiple_choice` is processed
- **THEN** the response contains `suggestion`, `selected_ids` as a list of matching `choices[].id` values (or `null`), and `citations`

### Requirement: LLM Reasoning Field

The system SHALL include an optional `reasoning` field on both the single (`POST /suggest`) and batch (`POST /suggest/batch`) suggestion responses, allowing the LLM to surface its interpretation, confidence level, and any caveats.

#### Scenario: Reasoning provided when selection is null

- **WHEN** `selected_id` or `selected_ids` is `null`
- **THEN** `reasoning` MUST be present and non-empty, explaining why no selection could be made

#### Scenario: Reasoning provided when evidence is ambiguous or synthesized

- **WHEN** the LLM draws on multiple sources or makes a judgment call
- **THEN** `reasoning` SHOULD describe how the sources were interpreted and why this answer was chosen

#### Scenario: Reasoning absent when answer is straightforward

- **WHEN** the LLM generates a confident suggestion from a single clear source
- **THEN** `reasoning` MAY be `null` or omitted

#### Scenario: Reasoning present on single-question endpoint

- **WHEN** a `POST /suggest` response is returned
- **THEN** the response includes a `reasoning` field (optional string) alongside `answer` and `citations`
