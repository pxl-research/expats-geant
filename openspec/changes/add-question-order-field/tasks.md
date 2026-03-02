## 1. Model

- [x] 1.1 Add `order: int = Field(0, ...)` to `Question` in `m_shared/models/question.py`
- [x] 1.2 Update the `json_schema_extra` example to include `"order": 0`

## 2. Adapters

- [x] 2.1 **LimeSurvey** — import: set `question.order = q_meta["order"]`; remove `"order"` from `metadata`
- [x] 2.2 **LimeSurvey** — export: write `question_order` from `question.order` instead of `question.metadata.get("order", 0)`
- [x] 2.3 **SurveyMonkey** — import: set `question.order` from the platform `position` field
- [x] 2.4 **SurveyMonkey** — export: use `question.order` as `position` (keep enumeration fallback for order=0 ties)
- [x] 2.5 **QTI** — import: assign `order` from enumeration index within the section
- [x] 2.6 **Qualtrics** — import: assign `order` from enumeration index within the block

## 3. Tests

- [x] 3.1 Unit test: `Question` model accepts and serializes `order`
- [x] 3.2 Unit test: LimeSurvey round-trip preserves question order
- [x] 3.3 Unit test: SurveyMonkey import sets `question.order` from `position`

## 4. Docs / Spec

- [x] 4.1 Update `data-models` spec (MODIFIED Requirement: Question Model)
