# Change: Add order field to Question model

## Why

Multiple adapters already track question ordering but store it inconsistently — LimeSurvey
persists it in `metadata["order"]`, SurveyMonkey derives it by enumeration at export time,
and QTI/Qualtrics rely on implicit list position with no stored value. This means round-trips
can silently lose platform-native question ordering. `Section` already has a first-class
`order: int` field; `Question` should be consistent.

## What Changes

- Add `order: int = 0` to the `Question` model (default 0 preserves backward compatibility)
- LimeSurvey adapter: read/write `question.order` instead of `metadata["order"]` for question ordering
- SurveyMonkey adapter: persist imported `position` into `question.order`; export `question.order` (falling back to enumeration index)
- QTI adapter: assign `order` from enumeration index on import; no export change needed (document order is canonical in QTI)
- Qualtrics adapter: assign `order` from enumeration index on import; no export change needed
- Update `data-models` spec to reflect the new field on Question

## Impact

- Affected specs: `data-models`
- Affected code: `m_shared/models/question.py`, `m_shared/adapters/limesurvey.py`, `m_shared/adapters/surveymonkey.py`, `m_shared/adapters/qti.py`, `m_shared/adapters/qualtrics.py`
- No breaking change: `order` defaults to `0`, so existing instantiation sites continue to work without changes
