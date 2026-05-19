# Change: Add descriptive question type

## Why

All four supported platforms have a concept of display-only informational blocks
(LimeSurvey type `X`, Qualtrics `DB`, SurveyMonkey `presentation` family, QTI
non-interactive items). These are currently silently dropped during import, which
degrades round-trip fidelity and loses context that survey designers intentionally
placed. A Shape API client has also requested the ability to create informational
blocks via the design assistant.

## What Changes

- Add `DESCRIPTIVE = "descriptive"` to the `QuestionType` enum
- Set `required` to `False` by default for descriptive questions
- Update all four adapter type maps (import + export) to map the platform-native
  descriptive type to/from the new internal type
- Cue UI: render descriptive items as static text with no input control and no
  suggestion zone
- Cue RAG pipeline: skip descriptive items (no answer to suggest)
- Shape engines: allow the LLM to create and suggest descriptive blocks; skip
  question-specific validation rules for descriptive items
- Text content is plain text (consistent with all other question types)

## Impact

- Affected specs: `data-models`, `questionnaire-design`, `survey-ui`
- Affected code: `m_shared/models/question.py`, all four adapters, `cue_api/`
  (batch suggest filter), `cue_ui/templates/survey.html`, Shape engines
- No breaking changes — additive only; existing surveys are unaffected
