# Change: Implement M-Chat Questionnaire Design Module

## Why

M-Chat is the second core module of the platform (alongside M-Autofill) and is required for Phase 4. It does not yet exist beyond a placeholder. Without it, the pilot cannot cover the administrator-facing use case: helping survey designers create better questionnaires faster.

## What Changes

- Implement `m_chat/` module with suggestion, validation, and tagging engines
- Add `create_survey()` capability to platform adapters (LimeSurvey + Qualtrics → API push; SurveyMonkey + QTI → file download fallback)
- Add two API layers:
  - **Context-free stateless endpoints**: `import`, `export`, `create` — no session required; suitable for institutional integrations
  - **Context-aware tool endpoints**: `suggest`, `validate`, `tag` — work standalone OR with a `session_id` for richer, survey-aware reasoning
  - **Conversational session API**: `chat` — LLM-driven iterative questionnaire authoring with full session state
- Add document upload for survey drafting: admins upload a slide deck, Word doc, or PDF; the LLM extracts structure and generates an initial question draft
- Add per-session storage (same isolation pattern as M-Autofill): draft survey, tag vocabulary, conversation history, uploaded documents
- Add `m_chat_ui/` web interface: simple conversational chat UI for the pilot, parallel to the existing `m_ui/` for M-Autofill
- Ground validation engine rules in `docs/SURVEY_DESIGN_GUIDELINES.md`

## Impact

- Affected specs: `questionnaire-design` (new and modified requirements)
- Affected code: new `m_chat/` module, `m_shared/adapters/` (create capability), `docker-compose.yml` (new service), new `m_chat_ui/` service
- No breaking changes to existing M-Autofill or M-Shared code
- Reuses: `m_shared/session/manager.py`, `m_shared/vectordb/utils.py` (chunking/extraction), `m_shared/llm/client.py`, `m_shared/auth/middleware.py`
