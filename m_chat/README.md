# M-Chat: Administrator Questionnaire Design Co-Pilot

> ⚠️ **Not yet implemented.** This module is planned for a future phase. The structure and API endpoints described below are the intended design, not current working code. Only `__init__.py` and `manager.py` exist at this stage.

An AI-powered assistant that accelerates questionnaire and survey design with guardrails, consistency checks, intelligent tagging, and summarization.

## Overview

M-Chat is a co-pilot for survey administrators and form designers. It helps create better questionnaires faster by:

1. **Suggesting** clearer, more consistent questions
2. **Checking** alignment with style guidelines and QTI 3.0 standards
3. **Tagging** questions automatically for organization and categorization
4. **Summarizing** questionnaires and identifying gaps or redundancies
5. **Expressing** simple evaluation rules

M-Chat is not a replacement for human judgment—it augments the design process, reducing manual work and improving cross-survey comparability.

## Key Features

✏️ **Intelligent Suggestions**

- Propose reworded questions for clarity and consistency
- Generate alternative question variants; retry if unsatisfied with initial suggestion
- Suggest answer options and branching logic
- Recommend tags and metadata based on question content

🛡️ **Guardrails & Compliance**

- Enforce institutional style guidelines
- Validate against QTI 3.0 standard (common question types)
- Check for biased or unclear phrasing
- Ensure accessibility standards

📊 **Tagging & Metadata**

- Auto-suggest tags based on question text and context
- Batch tagging across sections or entire questionnaire
- Organize questions for comparison and reuse

## Module Structure

```
m_chat/
├── __init__.py
└── manager.py               # Placeholder session/state manager
```

> The files below are **planned** (not yet created):
> `questionnaire_parser.py`, `suggestion_engine.py`, `validation_engine.py`, `tagging_engine.py`, `api.py`

## API Endpoints

(Examples; final design TBD)

```
POST /questionnaires/suggest
  - Input: question text, context (section, existing questions)
  - Returns: suggested improvements, reasoning

POST /questionnaires/validate
  - Input: questionnaire (QTI or internal format)
  - Returns: validation errors, warnings, compliance issues

POST /questionnaires/tag
  - Input: question(s) or full questionnaire
  - Returns: suggested tags, metadata

POST /questionnaires/export
  - Input: questionnaire (internal format)
  - Returns: QTI 3.0-compliant XML export

POST /questionnaires/import
  - Input: QTI 3.0 XML
  - Returns: questionnaire in internal format
```

## Configuration

Environment variables:

- `OPENROUTER_API_KEY` — OpenRouter API key for LLM access
- `STYLE_GUIDE_PATH` — Path to institutional style guidelines (YAML/JSON)
- `LLM_MODEL` — Default model on OpenRouter (e.g., `openai/gpt-4`)

## Development

### Running Tests

> ⚠️ No tests exist yet for this module.

```bash
# When implemented, tests will be run from the repo root:
pytest tests/ -k "chat" -v
```

### Dependencies

See root `requirements.txt` for full list. Key libraries:

- `fastapi` — Web framework
- `openai` — LLM client (OpenAI-compatible)
- `pydantic` — Data validation & serialization

## Design Philosophy

- **Augmentation, not replacement**: Suggestions are advisory; humans make final decisions
- **Explainability**: Every suggestion includes reasoning
- **Style consistency**: Enforce institutional guidelines without crushing creativity
- **Simplicity**: Focus on common question types (open, multiple choice, single choice, ranking, scale); avoid QTI extensibility for MVP

## QTI 3.0 Support

M-Chat supports the most common QTI question types for PoC:

- Multiple choice (radioResponse, multipleChoice)
- Single choice (singleChoice)
- Open-ended (extendedTextInteraction)
- Ranking/Ordering (orderInteraction)
- Scale/Range (sliderInteraction)

Full QTI extensibility is out of scope for the PoC.

## Integration

M-Chat is designed as an embeddable SDK. Integrate via:

1. **REST API**: Call endpoints from admin interfaces or survey builders
2. **QTI 3.0**: Import/export questionnaires for tool interoperability
3. **Batch mode**: Process multiple questionnaires for consistency audits

See [M-Shared](../m_shared/README.md) for client SDKs and utilities.

## Testing Strategy

**Deterministic components** (required):

- Question parsing and serialization
- Validation rule checking
- QTI import/export correctness
- Tag application logic

**LLM components** (future):

- Suggestion quality and relevance
- Style guide adherence
- Grammar and clarity improvements
- Approach: Manual review for PoC; LLM-based evaluation frameworks post-PoC

## Quality Metrics (Pilot Phase)

- **Time saved**: How much faster can administrators design questionnaires?
- **Consistency**: Are suggested questions more aligned with style guidelines?
- **Completeness**: Does tagging help identify gaps or redundancies?
- **Adoption**: Do administrators use suggestions and how frequently?

## Roadmap

- ✅ Basic suggestion engine (question rewording, style checks)
- 🚧 QTI 3.0 import/export
- 🚧 Tag suggestion & batch tagging
- 📅 Advanced branching/conditional logic (future)
- 📅 Integration with institutional form builders (future)

## References

- [Project Context](../openspec/project.md)
- [M-Autofill Module](../m_autofill/README.md)
- [M-Shared Utilities](../m_shared/README.md)
- [QTI 3.0 Standard](https://www.imsglobal.org/spec/qti/v3p0/information-model)
