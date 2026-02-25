## ADDED Requirements

### Requirement: QTI-Inspired Assessment Input Format

The system SHALL accept questionnaire input in a simplified JSON format inspired by the QTI 3.0 (IMS Global / 1EdTech) standard.

The format supports flat item lists (via top-level `items`) or grouped items (via `sections`). Flat lists are normalized internally to a single implicit section.

Supported item types: `open_ended`, `single_choice`, `multiple_choice`, `ranking`, `slider`.

Field alignment with QTI 3.0:
- `assessment_id` → QTI `assessmentTest identifier`
- `sections[].id` → QTI `assessmentSection identifier`
- `items[].id` → QTI `assessmentItem identifier`
- `items[].prompt` → QTI `itemBody` prompt text
- `choices[].id` → QTI `simpleChoice identifier`
- `choices[].label` → QTI `simpleChoice` content

#### Scenario: Sectioned assessment input

- **WHEN** a request payload includes a `sections` array with items
- **THEN** the system parses each section and its items, preserving group structure for context injection

#### Scenario: Flat assessment input

- **WHEN** a request payload includes a top-level `items` array with no `sections`
- **THEN** the system normalizes the items into a single implicit section and processes them equivalently

#### Scenario: Optional context fields

- **WHEN** `context` (assessment level) or `title` (section level) are omitted
- **THEN** the system processes the request without them, without error

### Requirement: Structured Suggestion Response Format

The system SHALL return suggestions in a structured JSON format borrowing patterns from FHIR QuestionnaireResponse (item-keyed structure) and W3C Web Annotation Data Model (citation/source fragment model).

Response envelope fields: `assessment_id`, `session_id`, `generated_at`, `model`.
Per-item fields: `item_id`, `type`, `suggestion`, `selected_id`/`selected_ids` (choice types), `reasoning`, `citations`.

Field alignment with FHIR QuestionnaireResponse:
- `responses[].item_id` → FHIR `item.linkId`
- `suggestion` → FHIR `item.answer.valueString`
- `selected_id` → FHIR `item.answer.valueCoding.code`

Field alignment with W3C Web Annotation Data Model:
- `citations[].source` → W3C `target.source`
- `citations[].excerpt` → W3C `target.selector.TextQuoteSelector.exact`
- `citations[].position` → W3C `target.selector.FragmentSelector` (normalized 0.0–1.0)
- `suggestion` → W3C annotation `body.value`

#### Scenario: Response keyed by item ID

- **WHEN** a batch suggest response is returned
- **THEN** each item in `responses` contains an `item_id` matching the corresponding input item `id`

#### Scenario: Citation includes source fragment

- **WHEN** a citation is generated
- **THEN** it contains `source` (filename), `excerpt` (exact text from document), and `position` (float 0.0–1.0)

#### Scenario: Response is migration-ready

- **WHEN** the response format is used by an external consumer
- **THEN** each field maps directly to a corresponding field in FHIR QuestionnaireResponse or W3C Web Annotation without data loss, enabling future format migration without breaking changes

### Requirement: Format Standards Documentation

The system SHALL maintain documentation of the I/O format standards used, their origins, and their migration paths, so that institutional integrators can evaluate compatibility.

#### Scenario: Standards reference available

- **WHEN** a developer or integrator reviews the project
- **THEN** they can find in `openspec/specs/interchange-formats/` the rationale for each format choice, the standards consulted, and the field-level mappings to those standards
