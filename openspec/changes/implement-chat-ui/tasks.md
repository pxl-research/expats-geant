## 0. Prerequisites
- [x] 0.1 `implement-chat-api` implemented and merged

## 1. Spec
- [x] 1.1 Spec delta validated: `openspec validate implement-chat-ui --strict`

## 2. Module Scaffold
- [x] 2.1 Create `m_chat_ui/` package: `main.py`, `router.py`, `api_client.py`
- [x] 2.2 Add `m_chat_ui/requirements.txt` (fastapi, jinja2, httpx, python-multipart)
- [x] 2.3 Set `MCHAT_API_URL` env var in `docker-compose.yml` for UI → API communication

## 3. API Client (`m_chat_ui/api_client.py`)
- [x] 3.1 `create_session() -> str` (session_id)
- [x] 3.2 `list_sessions() -> list[dict]`
- [x] 3.3 `send_message(session_id, message) -> dict` (message + survey_updated)
- [x] 3.4 `get_survey(session_id) -> dict`
- [x] 3.5 `get_style(session_id) -> dict`
- [x] 3.6 `update_style(session_id, language, free_text) -> None`
- [x] 3.7 `upload_style_doc(session_id, file_bytes, filename) -> str` (summary)
- [x] 3.8 `upload_content_doc(session_id, file_bytes, filename) -> str` (topic summary)
- [x] 3.9 `export_survey(session_id, format) -> str` (file content)
- [x] 3.10 `create_survey(session_id, format) -> dict` (survey_id or file content)
- [x] 3.11 `reset_session(session_id) -> None`
- [x] 3.12 `delete_session(session_id) -> None`

## 4. Templates
- [x] 4.1 `base.html` — shared layout and static asset links
- [x] 4.2 `index.html` — landing page: list active sessions with resume links + "Start new survey" button
- [x] 4.3 `setup.html` — style profile setup:
  - Language selector (dropdown, default English)
  - Optional free-text box for style preferences
  - Optional style guide document upload (HTMX partial — shows extracted summary inline after upload)
  - "Start chatting" and "Skip" buttons
- [x] 4.4 `chat.html` — main chat interface:
  - Message input and send button
  - Scrollable conversation history
  - Collapsible survey preview sidebar (current draft as structured list)
  - Language/style indicator in header with "Edit style" link
  - "Reset draft" and "End session" buttons
  - "Export / Publish" button linking to export page
- [x] 4.5 `export.html` — platform selector dropdown + export/create action:
  - Shows "Push to platform" for API-backed adapters (LimeSurvey, Qualtrics)
  - Shows "Download file" for file-fallback adapters (SurveyMonkey, QTI)
  - Displays result (survey ID or download link)

## 5. Routes
- [x] 5.1 `GET /` — landing page (list sessions for authenticated user)
- [x] 5.2 `POST /sessions` — create session; redirect to setup
- [x] 5.3 `GET /session/{session_id}/setup` — render style setup page
- [x] 5.4 `POST /session/{session_id}/setup` — save language + free text; redirect to chat
- [x] 5.5 `POST /session/{session_id}/setup/style-doc` (HTMX) — upload style guide; return summary fragment
- [x] 5.6 `GET /session/{session_id}/chat` — render chat page
- [x] 5.7 `POST /session/{session_id}/chat` (HTMX) — send message; return updated conversation fragment
- [x] 5.8 `POST /session/{session_id}/upload` (HTMX) — upload content document; return topic summary fragment
- [x] 5.9 `GET /session/{session_id}/export` — render export page
- [x] 5.10 `POST /session/{session_id}/export` — trigger export or create; return result fragment
- [x] 5.11 `POST /session/{session_id}/reset` — reset draft; redirect to chat
- [x] 5.12 `DELETE /session/{session_id}` — terminate session; redirect to landing

## 6. Docker & Deployment
- [x] 6.1 Create `m_chat_ui/Dockerfile` (python:3.11-slim, uvicorn, port 8004)
- [x] 6.2 Register `m_chat_ui` service in `docker-compose.yml` with env vars and healthcheck
- [ ] 6.3 Verify full stack (`docker-compose up`): all services healthy, UI accessible

## 7. Tests
- [x] 7.1 Unit tests for `api_client` with mocked HTTP responses (19 tests — `tests/test_chat_ui.py`)
- [x] 7.2 Integration test: full flow — create session → setup style → upload doc → chat → export
- [x] 7.3 Integration test: resume existing session from landing page
- [x] 7.4 Integration test: reset draft → continue chatting

## Definition of Done
- [x] All routes rendering correctly
- [ ] Full authoring flow working end-to-end in browser
- [ ] Session resume working from landing page
- [ ] Style setup skippable; defaults applied correctly
- [ ] Docker build verified; full stack runs with `docker-compose up`
- [ ] `openspec validate implement-chat-ui --strict` passes
