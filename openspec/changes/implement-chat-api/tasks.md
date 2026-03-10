## 0. Prerequisites
- [ ] 0.1 `implement-chat-engines` implemented and merged

## 1. Spec & Design
- [x] 1.1 Write `design.md` (API layers, adapter create, LLM orchestration)
- [ ] 1.2 Spec delta validated: `openspec validate implement-chat-api --strict`

## 2. Adapter `create` Capability
- [ ] 2.1 Add `create_survey(survey: Survey) -> str` to `SurveyAdapter` base class (`m_shared/adapters/base.py`)
  - [ ] 2.1a Default implementation raises `NotImplementedError`
  - [ ] 2.1b Update `docs/ADAPTERS.md` with `create` capability contract and return value semantics
- [ ] 2.2 LimeSurvey adapter
  - [ ] 2.2a `add_survey` → `add_group` per section → `add_question` per question via RemoteControl 2 API
  - [ ] 2.2b Return platform survey ID (sid)
  - [ ] 2.2c Add `"create"` to `capabilities()`
- [ ] 2.3 Qualtrics adapter
  - [ ] 2.3a `POST /surveys` to Qualtrics API v3 with serialized payload
  - [ ] 2.3b Return Qualtrics survey ID
  - [ ] 2.3c Add `"create"` to `capabilities()`
- [ ] 2.4 SurveyMonkey and QTI adapters — file download fallback
  - [ ] 2.4a `create_survey()` delegates to `export_survey()` and returns file content
  - [ ] 2.4b Add `"create"` to `capabilities()`
- [ ] 2.5 Unit tests for `create_survey` on all four adapters (mocked HTTP)
- [ ] 2.6 Integration test: LimeSurvey create flow with mock RemoteControl 2 API

## 3. FastAPI Application (`m_chat/api.py`)
- [ ] 3.1 Initialise FastAPI app with CORS, auth middleware, error handlers
- [ ] 3.2 Context-free endpoints
  - [ ] 3.2a `POST /import` — parse platform file → Survey JSON
  - [ ] 3.2b `POST /export` — Survey JSON → platform file content
  - [ ] 3.2c `POST /create` — Survey JSON → API push or file download based on adapter capability
- [ ] 3.3 Context-aware tool endpoints
  - [ ] 3.3a `POST /suggest` — with and without `session_id`
  - [ ] 3.3b `POST /validate` — accepts `{ "question": {...} }` or `{ "survey": {...} }`; with and without `session_id`
  - [ ] 3.3c `POST /tag` — with and without `session_id`; updates tag vocabulary when session provided
  - [ ] 3.3d Shared helper: `get_session_context(session_id) -> SessionContext | None`
- [ ] 3.4 Integration tests for all tool endpoints: stateless and session-aware variants (30+ tests)

## 4. Conversational API
- [ ] 4.1 Session lifecycle endpoints
  - [ ] 4.1a `POST /chat/sessions` — create session linked to JWT user_id; initialise style profile with defaults
  - [ ] 4.1b `GET /chat/sessions` — list active sessions for authenticated user
  - [ ] 4.1c `GET /chat/{session_id}` — session metadata + style profile summary
  - [ ] 4.1d `DELETE /chat/{session_id}` — terminate; wipe all session files
  - [ ] 4.1e `POST /chat/{session_id}/reset` — clear draft + tag vocabulary; preserve conversation + documents + style
- [ ] 4.2 Chat endpoint
  - [ ] 4.2a `POST /chat/{session_id}` — main turn handler
  - [ ] 4.2b Load conversation, draft survey (compact), style profile, tag vocabulary
  - [ ] 4.2c Build LLM prompt; execute server-side tool calls as needed
  - [ ] 4.2d Update draft survey if LLM proposes changes
  - [ ] 4.2e Append messages to conversation history
  - [ ] 4.2f Return `{ "message": "...", "survey_updated": bool }`
  - [ ] 4.2g `GET /chat/{session_id}/survey` — return current draft Survey JSON
- [ ] 4.3 Style profile endpoints
  - [ ] 4.3a `GET /chat/{session_id}/style`
  - [ ] 4.3b `PUT /chat/{session_id}/style` — partial update (language, free_text)
  - [ ] 4.3c `POST /chat/{session_id}/style/upload` — upload style guide doc; extract + summarise; store
- [ ] 4.4 Content document upload
  - [ ] 4.4a `POST /chat/{session_id}/upload` — upload PPTX/DOCX/PDF/TXT
  - [ ] 4.4b Extract via MarkItDown; chunk and store in `sessions/{session_id}/documents/`
  - [ ] 4.4c Return extracted topic summary
- [ ] 4.5 Integration tests: full authoring flows
  - [ ] 4.5a Start from scratch → chat → refine → export
  - [ ] 4.5b Upload content document → LLM proposes structure → refine → create on platform
  - [ ] 4.5c Import existing survey → validate → improve via chat → export
  - [ ] 4.5d Session isolation: two users cannot access each other's sessions
  - [ ] 4.5e Session resume: disconnect and reconnect within TTL window

## 5. Docker & Deployment
- [ ] 5.1 Create `m_chat/Dockerfile` (python:3.11-slim, uvicorn, port 8002)
- [ ] 5.2 Add `m_chat` service to `docker-compose.yml` with env vars and healthcheck
- [ ] 5.3 Verify build and run; test all endpoints via HTTP client

## Definition of Done
- [ ] All adapter create implementations complete and tested
- [ ] All REST endpoints (context-free + context-aware) passing integration tests
- [ ] Full conversational API passing integration tests (40+ tests total)
- [ ] Docker build verified; service starts and responds to healthcheck
- [ ] `openspec validate implement-chat-api --strict` passes
- [ ] No regressions in existing tests
