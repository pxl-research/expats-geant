## 0. Prerequisites
- [ ] 0.1 `implement-autofill-api-endpoints` archived (adapters, session infrastructure, and MarkItDown pipeline in place)

## 1. Spec & Design
- [x] 1.1 Write `design.md` (architecture, session storage, tool layers, adapter create capability)
- [ ] 1.2 Add spec deltas (`changes/implement-chat-design/specs/questionnaire-design/spec.md`)
- [ ] 1.3 Validate: `openspec validate implement-chat-design --strict`

## 2. Adapter `create` Capability
- [ ] 2.1 Add `create_survey(survey: Survey) -> str` to `SurveyAdapter` base class (`m_shared/adapters/base.py`)
  - [ ] 2.1a Default implementation raises `NotImplementedError`
  - [ ] 2.1b Update `ADAPTERS.md` with `create` capability contract and return value semantics
- [ ] 2.2 Implement `create_survey` for LimeSurvey adapter
  - [ ] 2.2a POST to RemoteControl 2: `add_survey` → `add_group` per section → `add_question` per question
  - [ ] 2.2b Return platform survey ID (sid) as string
  - [ ] 2.2c Add `"create"` to `capabilities()`
- [ ] 2.3 Implement `create_survey` for Qualtrics adapter
  - [ ] 2.3a POST to API v3 `/surveys` with serialized survey payload
  - [ ] 2.3b Return Qualtrics survey ID (e.g. `SV_xxxxxxxx`)
  - [ ] 2.3c Add `"create"` to `capabilities()`
- [ ] 2.4 Implement file-download fallback for SurveyMonkey and QTI adapters
  - [ ] 2.4a `create_survey()` calls `export_survey()` and returns file content string
  - [ ] 2.4b Add `"create"` to `capabilities()` with `"create_mode": "download"` in metadata
- [ ] 2.5 Unit tests for `create_survey` (mocked API calls) for all four adapters
- [ ] 2.6 Integration test: LimeSurvey create flow with mock RemoteControl 2 API

## 3. Session Infrastructure
- [ ] 3.1 Extend `m_shared/session/manager.py` for M-Chat session type
  - [ ] 3.1a Add `session_type` field (`"autofill"` | `"chat"`) to distinguish session kinds
  - [ ] 3.1b M-Chat sessions get `draft_survey.json`, `tag_vocabulary.json`, `conversation.json`, `style_profile.json` on creation
- [ ] 3.2 Add helper utilities for M-Chat session data (`m_chat/session.py`)
  - [ ] 3.2a `load_draft_survey(session_id) -> Survey | None`
  - [ ] 3.2b `save_draft_survey(session_id, survey: Survey) -> None`
  - [ ] 3.2c `load_tag_vocabulary(session_id) -> dict`
  - [ ] 3.2d `save_tag_vocabulary(session_id, vocab: dict) -> None`
  - [ ] 3.2e `load_conversation(session_id) -> list`
  - [ ] 3.2f `append_message(session_id, role: str, content: str) -> None`
  - [ ] 3.2g `load_style_profile(session_id) -> dict` — returns profile with defaults if not yet set
  - [ ] 3.2h `save_style_profile(session_id, profile: dict) -> None`
  - [ ] 3.2i Default style profile: `{ "language": "en", "free_text": "", "document_summary": "", "defaults_applied": true }`
- [ ] 3.3 Unit tests for session helpers (25+ tests)

## 4. Core Engines
- [ ] 4.1 Implement `m_chat/suggestion_engine.py`
  - [ ] 4.1a `suggest_question(question: Question, survey_context: Survey | None) -> list[str]`
  - [ ] 4.1b Returns alternative phrasings with reasoning
  - [ ] 4.1c When `survey_context` provided: includes survey topic and audience in LLM prompt
- [ ] 4.2 Implement `m_chat/validation_engine.py`
  - [ ] 4.2a Deterministic rule checks (no LLM): double-barreled detection, scale length, leading language patterns, Likert label completeness
  - [ ] 4.2b LLM-assisted checks: clarity, tone, bias, consistency with other questions (when survey provided)
  - [ ] 4.2c Rules grounded in `docs/SURVEY_DESIGN_GUIDELINES.md`
  - [ ] 4.2d `validate_question(question: Question, survey: Survey | None) -> list[ValidationIssue]`
  - [ ] 4.2e `validate_survey(survey: Survey) -> list[ValidationIssue]` (full survey scan)
- [ ] 4.3 Implement `m_chat/tagging_engine.py`
  - [ ] 4.3a `suggest_tags(question: Question, vocabulary: dict | None) -> list[str]`
  - [ ] 4.3b When `vocabulary` provided: pass existing tags to LLM, prefer reuse over new tags
  - [ ] 4.3c Normalize tags: lowercase, strip whitespace, deduplicate
- [ ] 4.4 Unit tests for each engine (20+ tests each)

## 5. Stateless & Context-Aware REST Endpoints (`m_chat/api.py`)
- [ ] 5.1 `POST /import` — parse platform file → Survey; returns Survey JSON
- [ ] 5.2 `POST /export` — Survey JSON → platform file; returns file content + format
- [ ] 5.3 `POST /create` — Survey JSON → push to platform or file download
  - [ ] 5.3a Select adapter from `format` param; call `create_survey()`
  - [ ] 5.3b Return `{ "survey_id": "...", "mode": "api" }` or `{ "file": "...", "mode": "download" }`
- [ ] 5.4 `POST /suggest` — question text → suggestions
  - [ ] 5.4a Without `session_id`: stateless, generic reasoning
  - [ ] 5.4b With `session_id`: load draft survey, pass as context
- [ ] 5.5 `POST /validate` — question or full survey → issues list
  - [ ] 5.5a Accepts either `{ "question": {...} }` or `{ "survey": {...} }`
  - [ ] 5.5b With `session_id`: validates against full session draft
- [ ] 5.6 `POST /tag` — question → suggested tags
  - [ ] 5.6a Without `session_id`: generic tag inference
  - [ ] 5.6b With `session_id`: load tag vocabulary, return consistent tags, update vocabulary
- [ ] 5.7 Auth middleware: apply existing `SessionMiddleware` from `m_shared/auth/middleware.py`
- [ ] 5.8 Integration tests for all endpoints (stateless and session-aware variants)

## 6. Conversational API
- [ ] 6.1 `POST /chat/sessions` — create new chat session (linked to JWT user_id); returns `session_id`; initialises style profile with defaults
- [ ] 6.1a `GET /chat/sessions` — list active sessions for the authenticated user (for landing page "resume" list)
- [ ] 6.1b `GET /chat/{session_id}/style` — return current style profile
- [ ] 6.1c `PUT /chat/{session_id}/style` — update style profile fields (language, free_text); partial update supported
- [ ] 6.1d `POST /chat/{session_id}/style/upload` — upload institutional style guide document (PDF, DOCX, TXT); extract text via MarkItDown; LLM summarises style rules into `document_summary`; store in `style_documents/`
- [ ] 6.2 `POST /chat/{session_id}` — send message, get response
  - [ ] 6.2a Load conversation history + draft survey + tag vocabulary
  - [ ] 6.2b Build LLM prompt (system context + compact survey JSON + history + user message)
  - [ ] 6.2c LLM response may trigger internal tool calls (suggest, validate, tag) — server-side only
  - [ ] 6.2d Update draft survey if LLM proposes changes; save to session
  - [ ] 6.2e Append both user message and assistant response to `conversation.json`
  - [ ] 6.2f Return `{ "message": "...", "survey_updated": bool }`
- [ ] 6.3 `GET /chat/{session_id}/survey` — return current draft Survey JSON
- [ ] 6.4 `POST /chat/{session_id}/upload` — upload source document
  - [ ] 6.4a Accept PPTX, DOCX, PDF, TXT
  - [ ] 6.4b Extract text via MarkItDown (reuse `m_shared/vectordb/utils.py`)
  - [ ] 6.4c Chunk and store in `sessions/{session_id}/documents/`
  - [ ] 6.4d Return extracted topic summary to be included in next chat turn context
- [ ] 6.5 `DELETE /chat/{session_id}` — terminate session; wipe all session files
- [ ] 6.5a `POST /chat/{session_id}/reset` — reset draft survey and tag vocabulary to empty; preserve conversation history and documents
- [ ] 6.6 Integration tests: full authoring flows
  - [ ] 6.6a Start from scratch → iterate via chat → export
  - [ ] 6.6b Upload document → LLM proposes structure → refine → create on platform
  - [ ] 6.6c Import existing survey → validate → improve via chat → export

## 7. M-Chat UI (`m_chat_ui/`)
- [ ] 7.1 Scaffold `m_chat_ui/` package: `main.py`, `router.py`, `api_client.py`
- [ ] 7.2 `api_client.py` — thin wrapper over M-Chat conversational API
  - [ ] 7.2a `create_session() -> session_id`
  - [ ] 7.2b `send_message(session_id, message) -> response`
  - [ ] 7.2c `get_survey(session_id) -> Survey`
  - [ ] 7.2d `upload_document(session_id, file_bytes, filename) -> topic_summary`
  - [ ] 7.2e `export_survey(session_id, format) -> file content`
  - [ ] 7.2f `create_survey(session_id, format) -> survey_id or file content`
- [ ] 7.3 Templates
  - [ ] 7.3a `base.html` — shared layout
  - [ ] 7.3b `index.html` — start new session or resume existing; option to upload a content document
  - [ ] 7.3c `setup.html` — style profile setup step shown after session creation: language selector (default English), optional free-text box, optional style guide document upload, skip/continue button
  - [ ] 7.3d `chat.html` — conversational interface (message input, response display, survey preview sidebar, language/style indicator with edit link)
  - [ ] 7.3e `export.html` — platform selector + export/create action
- [ ] 7.4 Routes
  - [ ] 7.4a `GET /` — landing page: list user's active sessions (resume) + option to start new
  - [ ] 7.4b `POST /sessions` — create session, redirect to style setup
  - [ ] 7.4c `POST /sessions/upload` — create session with content document, redirect to style setup
  - [ ] 7.4d `GET /session/{session_id}/setup` — render style profile setup page
  - [ ] 7.4e `POST /session/{session_id}/setup` — save language + free-text style; redirect to chat
  - [ ] 7.4f `POST /session/{session_id}/setup/style-doc` (HTMX) — upload style guide doc, show extracted summary for confirmation
  - [ ] 7.4d `GET /session/{session_id}/chat` — render chat page
  - [ ] 7.4e `POST /session/{session_id}/chat` (HTMX) — send message, return updated chat fragment
  - [ ] 7.4f `GET /session/{session_id}/export` — render export page
  - [ ] 7.4g `POST /session/{session_id}/export` — trigger export or create; return result
- [ ] 7.5 Add `m_chat_ui/Dockerfile` and register as `chat-ui` service in `docker-compose.yml`
- [ ] 7.6 Unit tests for `api_client` (mocked HTTP)
- [ ] 7.7 Integration test: upload document → chat → export flow

## 8. Docker & Deployment
- [ ] 8.1 Add `m_chat/Dockerfile`
- [ ] 8.2 Register `m_chat` and `m_chat_ui` services in `docker-compose.yml`
- [ ] 8.3 Set required env vars: `OIDC_ISSUER_URL`, `JWT_SECRET`, `OPENROUTER_API_KEY`
- [ ] 8.4 Verify full stack (`docker-compose up`) runs with all services healthy

## Definition of Done
- [ ] All implementation tasks complete
- [ ] All unit and integration tests passing
- [ ] `openspec validate implement-chat-design --strict` passes
- [ ] Docker build and run verified
- [ ] Stateless endpoints callable without session (verified via curl)
- [ ] Full chat authoring flow working end-to-end in `m_chat_ui`
- [ ] No critical security issues
