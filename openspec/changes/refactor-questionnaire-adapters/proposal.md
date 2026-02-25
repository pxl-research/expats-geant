# Change: Replace QTI-only I/O with platform-agnostic adapter pattern

## Why

The original spec treated QTI 3.0 as the primary interchange format for both import and export.
In practice, QTI models questions well but is weak on response/answer data and is not used by
mainstream survey platforms (Qualtrics, LimeSurvey, SurveyMonkey). Locking the architecture to
QTI would require survey administrators to convert their data before using the platform, which is
a significant adoption barrier.

## What Changes

- The internal data model (Survey → Section → Question → AnswerOption → Response) becomes the
  explicit **platform-agnostic common denominator**, informed by QTI and DDI but not bound to either
- QTI 3.0 import/export becomes **one adapter among several**, not the primary format
- A formal **Platform Adapter** abstraction is introduced: each adapter translates to/from a
  specific platform's format (QTI, Qualtrics, LimeSurvey, SurveyMonkey)
- Question validation is decoupled from QTI compliance — style/clarity checks remain; QTI
  compliance becomes an optional adapter-level concern
- The `metadata` dict on Question/AnswerOption/Survey is formalized as the escape hatch for
  platform-specific fields that don't map cleanly to the common model

## Impact

- Affected specs: `questionnaire-design`, `data-models`
- Affected code (Phase 4): `m_chat/qti_parser.py` → `m_chat/adapters/` (one file per platform)
- No breaking changes to existing models — the common denominator is already there
- **BREAKING** for Phase 4 file structure: `qti_parser.py` replaced by `adapters/` package
