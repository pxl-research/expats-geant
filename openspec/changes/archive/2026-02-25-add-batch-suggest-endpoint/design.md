# Design: Batch Suggest Endpoint — Format Decisions & Standards

## Context

The batch suggest endpoint introduces two new structured formats: an input format for submitting questionnaire items, and an output format for structured answer suggestions with citations. These formats need to be simple enough to implement quickly in the PoC, interoperable with institutional survey tools, and easy to migrate to stricter standards in future phases.

## Goals / Non-Goals

- **Goals:** Simple REST-friendly JSON I/O; QTI-aligned naming; transparent LLM reasoning; citeable sources; easy integration for pilot partners
- **Non-Goals:** Full QTI 3.0 compliance; XML support; scoring/grading semantics; re-ranking; streaming responses

---

## Input Format: QTI-Inspired JSON

### Decision
Use a simplified JSON subset inspired by QTI 3.0 (IMS Global / 1EdTech), not full QTI 3.0 XML.

### Rationale
QTI 3.0 is the project's stated interoperability standard (see `openspec/project.md`). However, QTI's native XML serialization is verbose and poorly suited to a REST API. The JSON subset retains QTI's conceptual structure (assessments → sections → items → choices) while remaining practical for direct API use.

### Key structural choices
- Top-level `sections` array for grouping related items (optional — callers may use a flat `items` array instead)
- Flat `items` at the top level are normalized internally to a single implicit section
- `type` values (`open_ended`, `single_choice`, `multiple_choice`, `ranking`, `slider`) map directly to the project's `QuestionType` enum in `m_shared/models/question.py`
- `choices` array uses `id` + `label` (maps to QTI `simpleChoice identifier` + content)
- `context` fields at assessment and section level feed into LLM prompt construction

### QTI 3.0 alignment
| Our field       | QTI 3.0 equivalent                        |
|-----------------|--------------------------------------------|
| `assessment_id` | `assessmentTest identifier`                |
| `sections[].id` | `testPart` / `assessmentSection identifier`|
| `items[].id`    | `assessmentItem identifier`                |
| `items[].prompt`| `itemBody` prompt text                     |
| `choices[].id`  | `simpleChoice identifier`                  |
| `choices[].label`| `simpleChoice` content                   |

### Migration path to full QTI 3.0
The JSON subset is a strict projection of QTI 3.0 concepts. Migration requires: wrapping in QTI XML envelope, converting `type` to QTI interaction types (`extendedTextInteraction`, `choiceInteraction`, etc.), and adding `responseDeclaration` blocks. No semantic changes to content.

---

## Output Format: Structured Suggestion Response

### Decision
Custom JSON format borrowing patterns from FHIR `QuestionnaireResponse` and W3C Web Annotation Data Model. Not a direct implementation of either.

### Rationale
No existing standard covers AI-generated answer suggestions with source citations for survey questions. Standards considered:

| Standard | Verdict |
|---|---|
| **QTI 3.0 AssessmentResult** | Designed for scored assessments (right/wrong). Semantically wrong for suggestions. |
| **FHIR QuestionnaireResponse** | Clean `item`-keyed response structure. Good structural pattern to borrow. Not adopted directly — healthcare domain baggage, dependency overhead. |
| **W3C Web Annotation Data Model** | Best model for citations: body (suggestion) pointing to a target (document fragment) via a selector. Adopted for citation field naming. |
| **DDI (Data Documentation Initiative)** | Dominant standard in European research survey archives (CESSDA, GÉANT partners). Too documentation-oriented for real-time API responses. Naming conventions adopted. |
| **xAPI / Tin Can** | Learning analytics. Wrong abstraction layer. |

### Key field decisions

**`suggestion` (string, always present)**
Human-readable answer text. Universal across all question types. Safe to display directly. Inspired by DDI response value concept.

**`selected_id` / `selected_ids` (string / list, choice types only)**
Machine-parseable mapping back to input `choices[].id`. Enables programmatic form-filling. Absent for `open_ended`. `null` when the LLM cannot confidently select a choice.

**`reasoning` (string, optional)**
LLM-generated explanation of its interpretation, confidence level, or uncertainty. Present on both the single (`POST /suggest`) and batch (`POST /suggest/batch`) endpoints. Especially important when `selected_id` is `null`, evidence is ambiguous, or the answer synthesizes multiple sources. Central to the project's "explainability" goal (EXPAT = **Ex**plainable **A**utofill for **T**rustworthy Surveys). `null` when the answer is straightforward and self-evident from the citations.

**`citations[].excerpt` (string)**
Exact text fragment from the source document. Inspired by W3C Web Annotation `TextQuoteSelector`. Enables users to verify the source directly.

**`citations[].position` (float 0.0–1.0)**
Normalized document position. Display-agnostic — callers convert to percentage, page number, or timestamp as appropriate.

### FHIR QuestionnaireResponse alignment
| Our field        | FHIR equivalent                     |
|------------------|-------------------------------------|
| `assessment_id`  | `questionnaire` (canonical URL)     |
| `responses[].item_id` | `item.linkId`                  |
| `suggestion`     | `item.answer.valueString`           |
| `selected_id`    | `item.answer.valueCoding.code`      |

### W3C Web Annotation alignment
| Our field              | W3C Annotation equivalent          |
|------------------------|------------------------------------|
| `citations[].source`   | `target.source`                    |
| `citations[].excerpt`  | `target.selector.TextQuoteSelector.exact` |
| `citations[].position` | `target.selector.FragmentSelector` |
| `suggestion`           | `body.value`                       |

### Migration path
- **To DDI:** `assessment_id` → DDI study reference; `item_id` → DDI variable name; `suggestion` → DDI response value. Additive wrapping, no field renames.
- **To W3C Web Annotation:** Each citation becomes an `Annotation` object; `suggestion` becomes the annotation `body`; source + excerpt + position become the `target` selectors. Requires restructuring but no data loss.
- **To FHIR:** Wrap `responses` array as FHIR `item` array; add FHIR resource envelope. `selected_id` maps to `valueCoding`.

---

## Risks / Trade-offs

- **Context window cost:** Passing sibling question prompts as context increases token usage per request. Mitigation: limit context to section title + question prompts only (not choices or metadata). Evaluate during pilot.
- **Choice mapping accuracy:** LLM may mis-map to a `choice.id` not present in the input. Mitigation: validate `selected_id` against input choices in the response serializer; fall back to `null` + remark if invalid.
- **Section-less input normalization:** Flat `items` are wrapped in an implicit section. If callers later add sections, the normalization is transparent. No migration needed.

## Open Questions

- Should `ranking` questions return `selected_ids` as an ordered list (reflecting rank order)? Currently treated like `multiple_choice`.
- Should `slider` questions return a `selected_value` (float) instead of `selected_id`? Not yet specified.
