# Change: Implement M-Chat Core Engines

## Why

M-Chat has no implementation beyond placeholders. This change builds the foundational layer:
session infrastructure, the three intelligent engines (suggestion, validation, tagging), and
the style profile system. All subsequent M-Chat changes depend on this foundation.

## What Changes

- Session infrastructure for M-Chat: per-user session folders with draft survey, tag
  vocabulary, style profile, conversation history, and uploaded documents
- Suggestion engine: LLM-based question rewording, with and without survey context
- Validation engine: deterministic rule checks (double-barreling, scale length, leading
  language) + LLM-assisted checks (clarity, tone, bias); rules grounded in
  `docs/SURVEY_DESIGN_GUIDELINES.md`
- Tagging engine: tag suggestion with session vocabulary awareness for cross-question
  consistency
- Style profile system: language setting (default English), free-text style preferences,
  and optional institutional style guide document upload; sensible defaults when not provided

## Impact

- Affected specs: `questionnaire-design` (ADDED: Session Style Profile and Language)
- Affected code: new `m_chat/` module files (`session.py`, `suggestion_engine.py`,
  `validation_engine.py`, `tagging_engine.py`); extends `m_shared/session/manager.py`
- No breaking changes to existing M-Autofill or M-Shared code
- Reuses: `m_shared/session/manager.py`, `m_shared/vectordb/utils.py`, `m_shared/llm/client.py`
