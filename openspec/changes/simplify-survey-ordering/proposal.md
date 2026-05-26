# Change: Make list position the single source of truth for survey ordering

## Why

A user reordered questions through chat. The LLM patched each question's
`order` field — but the preview, QTI export, and SurveyMonkey export all
render by **list position** and ignore `order`. The edit reported success and
changed nothing visible. Root cause: two competing notions of order (the
`order: int` field vs. list position) that are never kept in sync, plus an
editable `order` knob that no consumer actually reads. Sections carry the same
latent hazard — `surveymonkey.py:170` is the lone reader of `section.order`,
so a moved section would export to a different order than QTI/preview show.

## What Changes

- **BREAKING (internal model):** Remove the `order` field from `Question` and
  `Section`. List position within `section.questions` and `survey.sections`
  becomes the sole source of truth for ordering.
- Add `move_question` and `move_section` mutation tools (and matching HTTP
  endpoints) that change list position — the actual reorder mechanism that was
  missing.
- Remove `order` from `QuestionPatch` / `SectionPatch` and from the tool-schema
  field descriptions, so editing order can no longer be a silent no-op.
- Export adapters that emit an explicit platform order field SHALL compute it
  from list index instead of the model field: SurveyMonkey section position
  (`surveymonkey.py:170`) and LimeSurvey `group_order` / `question_order`
  (`limesurvey.py:340,354`). QTI and Qualtrics need no change (they encode order
  by element/array position only).
- Importers: remove the `order=` construction kwargs. All four already build
  their lists in display order (verified — see design.md), so **no import
  ordering logic changes are required**.
- Chat system prompt: replace the delete-then-add "move" instruction with
  `move_question` / `move_section`.

## Impact

- Affected specs: `data-models` (model shape + ordering invariant),
  `questionnaire-design` (adapter round-trip + new reorder operations).
- Affected code: `m_shared/models/question.py`, `section.py`;
  `m_shared/adapters/{surveymonkey,qti,qualtrics,limesurvey}.py`;
  `shape_api/mutations.py`, `models.py`, `tools.py`, `conversation.py`,
  `routes/chat.py`; `docs/SHAPE_API.md`; tests.
- **Depends on** `add-granular-survey-mutations` being archived first: this
  change extends that change's mutation tools / endpoints / patch models.
