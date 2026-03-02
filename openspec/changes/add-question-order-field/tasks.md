## 1. Model

- [ ] 1.1 Add `order: int = Field(0, ...)` to `Question` in `m_shared/models/question.py`
- [ ] 1.2 Update the `json_schema_extra` example to include `"order": 0`

## 2. Adapters

- [ ] 2.1 **LimeSurvey** — import: set `question.order = q_meta["order"]`; remove `"order"` from `metadata`
- [ ] 2.2 **LimeSurvey** — export: write `question_order` from `question.order` instead of `question.metadata.get("order", 0)`
- [ ] 2.3 **SurveyMonkey** — import: set `question.order` from the platform `position` field
- [ ] 2.4 **SurveyMonkey** — export: use `question.order` as `position` (keep enumeration fallback for order=0 ties)
- [ ] 2.5 **QTI** — import: assign `order` from enumeration index within the section
- [ ] 2.6 **Qualtrics** — import: assign `order` from enumeration index within the block

## 3. Tests

- [ ] 3.1 Unit test: `Question` model accepts and serializes `order`
- [ ] 3.2 Unit test: LimeSurvey round-trip preserves question order
- [ ] 3.3 Unit test: SurveyMonkey import sets `question.order` from `position`

## 4. Docs / Spec

- [ ] 4.1 Update `data-models` spec (MODIFIED Requirement: Question Model)
