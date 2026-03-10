## 0. Prerequisites
- [ ] 0.1 `implement-autofill-api-endpoints` archived (shared session infrastructure and MarkItDown pipeline confirmed in place)

## 1. Spec & Design
- [x] 1.1 Write `design.md` (overall M-Chat architecture, session layout, engine decisions)
- [ ] 1.2 Spec delta validated: `openspec validate implement-chat-engines --strict`

## 2. Session Infrastructure
- [ ] 2.1 Extend `m_shared/session/manager.py` for M-Chat session type
  - [ ] 2.1a Add `session_type` field (`"autofill"` | `"chat"`) to session metadata
  - [ ] 2.1b M-Chat session creation initialises all required files with empty/default values
- [ ] 2.2 Implement `m_chat/session.py` — session data helpers
  - [ ] 2.2a `load_draft_survey(session_id) -> Survey | None`
  - [ ] 2.2b `save_draft_survey(session_id, survey: Survey) -> None`
  - [ ] 2.2c `load_tag_vocabulary(session_id) -> dict`
  - [ ] 2.2d `save_tag_vocabulary(session_id, vocab: dict) -> None`
  - [ ] 2.2e `load_conversation(session_id) -> list`
  - [ ] 2.2f `append_message(session_id, role: str, content: str) -> None`
  - [ ] 2.2g `load_style_profile(session_id) -> dict` — returns defaults if not set
  - [ ] 2.2h `save_style_profile(session_id, profile: dict) -> None`
  - [ ] 2.2i Default style profile: `{ "language": "en", "free_text": "", "document_summary": "", "defaults_applied": true }`
- [ ] 2.3 Unit tests for session helpers (25+ tests, including TTL, isolation, defaults)

## 3. Style Profile System
- [ ] 3.1 Implement style guide document processing (`m_chat/style.py`)
  - [ ] 3.1a Extract text from uploaded style guide doc via MarkItDown (`m_shared/vectordb/utils.py`)
  - [ ] 3.1b LLM call: summarise extracted text into concise style rules
  - [ ] 3.1c Store summary in `style_profile.json` under `document_summary`
  - [ ] 3.1d Save uploaded file to `sessions/{session_id}/style_documents/`
- [ ] 3.2 Implement `build_style_context(profile: dict) -> str` — formats profile into LLM system prompt fragment
- [ ] 3.3 Unit tests for style processing (10+ tests)

## 4. Suggestion Engine
- [ ] 4.1 Implement `m_chat/suggestion_engine.py`
  - [ ] 4.1a `suggest_question(question: Question, survey_context: Survey | None, style_profile: dict | None) -> list[SuggestionResult]`
  - [ ] 4.1b `SuggestionResult`: phrasing (str), reasoning (str)
  - [ ] 4.1c Without context: single-question prompt, generic reasoning
  - [ ] 4.1d With survey context: include compact survey summary (title + question texts) in prompt
  - [ ] 4.1e Style profile context always included when provided
- [ ] 4.2 Unit tests (20+ tests: with/without context, with/without style, edge cases)

## 5. Validation Engine
- [ ] 5.1 Implement `m_chat/validation_engine.py`
  - [ ] 5.1a `ValidationIssue`: question_id (str), severity (`"error"` | `"warning"` | `"info"`), code (str), message (str)
  - [ ] 5.1b Deterministic checks (no LLM):
    - Double-barreled detection (conjunction patterns: "and", "or" joining two clauses)
    - Scale length check (< 4 or > 7 answer options flagged)
    - Leading language keyword list (e.g. "don't you think", "obviously")
    - Likert label completeness (if single_choice with 4–7 options, all should have labels)
  - [ ] 5.1c LLM-assisted checks (when survey provided or session available):
    - Clarity and ambiguity
    - Tone and bias
    - Cross-question consistency (duplicate intent, order effects)
  - [ ] 5.1d `validate_question(question: Question, survey: Survey | None, style_profile: dict | None) -> list[ValidationIssue]`
  - [ ] 5.1e `validate_survey(survey: Survey, style_profile: dict | None) -> list[ValidationIssue]`
- [ ] 5.2 Unit tests (25+ tests: each deterministic rule, LLM-assisted with mock, edge cases)

## 6. Tagging Engine
- [ ] 6.1 Implement `m_chat/tagging_engine.py`
  - [ ] 6.1a `suggest_tags(question: Question, vocabulary: dict | None, style_profile: dict | None) -> list[str]`
  - [ ] 6.1b Without vocabulary: infer tags from question text alone
  - [ ] 6.1c With vocabulary: pass existing tags as context, prefer reuse
  - [ ] 6.1d Normalise tags: lowercase, strip whitespace, deduplicate
  - [ ] 6.1e `update_vocabulary(vocab: dict, new_tags: list[str], question_id: str) -> dict`
- [ ] 6.2 Unit tests (20+ tests: with/without vocabulary, normalisation, vocabulary update)

## Definition of Done
- [ ] All session helpers implemented and tested
- [ ] Style profile system implemented and tested
- [ ] All three engines implemented with full unit test coverage
- [ ] All tests passing (target: 80+ tests)
- [ ] `openspec validate implement-chat-engines --strict` passes
- [ ] No regressions in existing M-Autofill or M-Shared tests
