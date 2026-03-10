## 0. Prerequisites
- [ ] 0.1 `implement-autofill-api-endpoints` archived (shared session infrastructure and MarkItDown pipeline confirmed in place)

## 1. Spec & Design
- [x] 1.1 Write `design.md` (overall M-Chat architecture, session layout, engine decisions)
- [x] 1.2 Spec delta validated: `openspec validate implement-chat-engines --strict`

## 2. Session Infrastructure
- [x] 2.1 Extend `m_shared/session/manager.py` for M-Chat session type
  - [x] 2.1a Add `session_type` field (`"autofill"` | `"chat"`) to session metadata
  - [x] 2.1b M-Chat session creation initialises all required files with empty/default values
- [x] 2.2 Implement `m_chat/session.py` — session data helpers
  - [x] 2.2a `load_draft_survey(session_id) -> Survey | None`
  - [x] 2.2b `save_draft_survey(session_id, survey: Survey) -> None`
  - [x] 2.2c `load_tag_vocabulary(session_id) -> dict`
  - [x] 2.2d `save_tag_vocabulary(session_id, vocab: dict) -> None`
  - [x] 2.2e `load_conversation(session_id) -> list`
  - [x] 2.2f `append_message(session_id, role: str, content: str) -> None`
  - [x] 2.2g `load_style_profile(session_id) -> dict` — returns defaults if not set
  - [x] 2.2h `save_style_profile(session_id, profile: dict) -> None`
  - [x] 2.2i Default style profile: `{ "language": "en", "free_text": "", "document_summary": "", "defaults_applied": true }`
- [x] 2.3 Unit tests for session helpers (25+ tests, including TTL, isolation, defaults)

## 3. Style Profile System
- [x] 3.1 Implement style guide document processing (`m_chat/style.py`)
  - [x] 3.1a Extract text from uploaded style guide doc via MarkItDown (`m_shared/vectordb/utils.py`)
  - [x] 3.1b LLM call: summarise extracted text into concise style rules
  - [x] 3.1c Store summary in `style_profile.json` under `document_summary`
  - [x] 3.1d Save uploaded file to `sessions/{session_id}/style_documents/`
- [x] 3.2 Implement `build_style_context(profile: dict) -> str` — formats profile into LLM system prompt fragment
- [x] 3.3 Unit tests for style processing (10+ tests)

## 4. Suggestion Engine
- [x] 4.1 Implement `m_chat/suggestion_engine.py`
  - [x] 4.1a `suggest_question(question: Question, survey_context: Survey | None, style_profile: dict | None) -> list[SuggestionResult]`
  - [x] 4.1b `SuggestionResult`: phrasing (str), reasoning (str)
  - [x] 4.1c Without context: single-question prompt, generic reasoning
  - [x] 4.1d With survey context: include compact survey summary (title + question texts) in prompt
  - [x] 4.1e Style profile context always included when provided
- [x] 4.2 Unit tests (20+ tests: with/without context, with/without style, edge cases)

## 5. Validation Engine
- [x] 5.1 Implement `m_chat/validation_engine.py`
  - [x] 5.1a `ValidationIssue`: question_id (str), severity (`"error"` | `"warning"` | `"info"`), code (str), message (str)
  - [x] 5.1b Deterministic checks (no LLM):
    - Double-barreled detection (conjunction patterns: "and", "or" joining two clauses)
    - Scale length check (< 4 or > 7 answer options flagged)
    - Leading language keyword list (e.g. "don't you think", "obviously")
    - Likert label completeness (if single_choice with 4–7 options, all should have labels)
  - [x] 5.1c LLM-assisted checks (when survey provided or session available):
    - Clarity and ambiguity
    - Tone and bias
    - Cross-question consistency (duplicate intent, order effects)
  - [x] 5.1d `validate_question(question: Question, survey: Survey | None, style_profile: dict | None) -> list[ValidationIssue]`
  - [x] 5.1e `validate_survey(survey: Survey, style_profile: dict | None) -> list[ValidationIssue]`
- [x] 5.2 Unit tests (25+ tests: each deterministic rule, LLM-assisted with mock, edge cases)

## 6. Tagging Engine
- [x] 6.1 Implement `m_chat/tagging_engine.py`
  - [x] 6.1a `suggest_tags(question: Question, vocabulary: dict | None, style_profile: dict | None) -> list[str]`
  - [x] 6.1b Without vocabulary: infer tags from question text alone
  - [x] 6.1c With vocabulary: pass existing tags as context, prefer reuse
  - [x] 6.1d Normalise tags: lowercase, strip whitespace, deduplicate
  - [x] 6.1e `update_vocabulary(vocab: dict, new_tags: list[str], question_id: str) -> dict`
- [x] 6.2 Unit tests (20+ tests: with/without vocabulary, normalisation, vocabulary update)

## Definition of Done
- [x] All session helpers implemented and tested
- [x] Style profile system implemented and tested
- [x] All three engines implemented with full unit test coverage
- [x] All tests passing (target: 80+ tests)
- [x] `openspec validate implement-chat-engines --strict` passes
- [x] No regressions in existing M-Autofill or M-Shared tests
