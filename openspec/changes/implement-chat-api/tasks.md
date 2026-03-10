## 0. Prerequisites
- [x] 0.1 `implement-chat-engines` implemented and merged

## 1. Spec & Design
- [x] 1.1 Write `design.md` (API layers, adapter create, LLM orchestration)
- [x] 1.2 Spec delta validated: `openspec validate implement-chat-api --strict`

## 2. Adapter `create` Capability
- [x] 2.1 Add `create_survey(survey: Survey) -> str` to `SurveyAdapter` base class (`m_shared/adapters/base.py`)
  - [x] 2.1a Default implementation raises `NotImplementedError`
  - [x] 2.1b Update `docs/ADAPTERS.md` with `create` capability contract and return value semantics
- [x] 2.2 LimeSurvey adapter
  - [x] 2.2a `add_survey` → `add_group` per section → `add_question` per question via RemoteControl 2 API
  - [x] 2.2b Return platform survey ID (sid)
  - [x] 2.2c Add `"create"` to `capabilities()`
- [x] 2.3 Qualtrics adapter
  - [x] 2.3a `POST /surveys` to Qualtrics API v3 with serialized payload
  - [x] 2.3b Return Qualtrics survey ID
  - [x] 2.3c Add `"create"` to `capabilities()`
- [x] 2.4 SurveyMonkey and QTI adapters — file download fallback
  - [x] 2.4a `create_survey()` delegates to `export_survey()` and returns file content
  - [x] 2.4b Add `"create"` to `capabilities()`
- [x] 2.5 Unit tests for `create_survey` on all four adapters (mocked HTTP)
- [x] 2.6 Integration test: LimeSurvey create flow with mock RemoteControl 2 API

## 3. FastAPI Application (`m_chat/api.py`)
- [x] 3.1 Initialise FastAPI app with CORS, auth middleware, error handlers
- [x] 3.2 Context-free endpoints
  - [x] 3.2a `POST /import` — parse platform file → Survey JSON
  - [x] 3.2b `POST /export` — Survey JSON → platform file content
  - [x] 3.2c `POST /create` — Survey JSON → API push or file download based on adapter capability
- [x] 3.3 Context-aware tool endpoints
  - [x] 3.3a `POST /suggest` — with and without `session_id`
  - [x] 3.3b `POST /validate` — accepts `{ "question": {...} }` or `{ "survey": {...} }`; with and without `session_id`
  - [x] 3.3c `POST /tag` — with and without `session_id`; updates tag vocabulary when session provided
  - [x] 3.3d Shared helper: `get_session_context(session_id) -> SessionContext | None`
- [x] 3.4 Integration tests for all tool endpoints: stateless and session-aware variants (42 tests)

## 4. Conversational API
- [x] 4.1 Session lifecycle endpoints
  - [x] 4.1a `POST /chat/sessions` — create session linked to JWT user_id; initialise style profile with defaults
  - [x] 4.1b `GET /chat/sessions` — list active sessions for authenticated user
  - [x] 4.1c `GET /chat/{session_id}` — session metadata + style profile summary
  - [x] 4.1d `DELETE /chat/{session_id}` — terminate; wipe all session files
  - [x] 4.1e `POST /chat/{session_id}/reset` — clear draft + tag vocabulary; preserve conversation + documents + style
- [x] 4.2 Chat endpoint
  - [x] 4.2a `POST /chat/{session_id}` — main turn handler
  - [x] 4.2b Load conversation, draft survey (compact), style profile, tag vocabulary
  - [x] 4.2c Build LLM prompt; execute server-side tool calls as needed
  - [x] 4.2d Update draft survey if LLM proposes changes
  - [x] 4.2e Append messages to conversation history
  - [x] 4.2f Return `{ "message": "...", "survey_updated": bool }`
  - [x] 4.2g `GET /chat/{session_id}/survey` — return current draft Survey JSON
- [x] 4.3 Style profile endpoints
  - [x] 4.3a `GET /chat/{session_id}/style`
  - [x] 4.3b `PUT /chat/{session_id}/style` — partial update (language, free_text)
  - [x] 4.3c `POST /chat/{session_id}/style/upload` — upload style guide doc; extract + summarise; store
- [x] 4.4 Content document upload
  - [x] 4.4a `POST /chat/{session_id}/upload` — upload PPTX/DOCX/PDF/TXT
  - [x] 4.4b Extract via MarkItDown; chunk and store in `sessions/{session_id}/documents/`
  - [x] 4.4c Return extracted topic summary
- [x] 4.5 Integration tests: full authoring flows
  - [x] 4.5a Start from scratch → chat → refine → export
  - [x] 4.5b Upload content document → LLM proposes structure → refine → create on platform
  - [x] 4.5c Import existing survey → validate → improve via chat → export
  - [x] 4.5d Session isolation: two users cannot access each other's sessions
  - [x] 4.5e Session resume: disconnect and reconnect within TTL window

## 5. Docker & Deployment
- [x] 5.1 Create `m_chat/Dockerfile` (python:3.12-slim, port 8003)
- [x] 5.2 Add `m_chat` service to `docker-compose.yml` with env vars and healthcheck
- [x] 5.3 Verify build and run; test all endpoints via HTTP client

## Definition of Done
- [x] All adapter create implementations complete and tested
- [x] All REST endpoints (context-free + context-aware) passing integration tests
- [x] Full conversational API passing integration tests (20 new tests; 62 total in m_chat)
- [x] Docker build verified; service starts and responds to healthcheck
- [x] `openspec validate implement-chat-api --strict` passes
- [x] No regressions in existing tests
