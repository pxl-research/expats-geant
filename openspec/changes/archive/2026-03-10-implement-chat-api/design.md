## Context

This change sits on top of `implement-chat-engines` and exposes the engines as a FastAPI
service. The key design decision is the two-tier API: context-free endpoints for integrations,
and context-aware endpoints that optionally use session state.

## Goals / Non-Goals

- **Goals:** All REST endpoints, conversational API, adapter create capability, Docker for m_chat
- **Non-Goals:** UI (next change), streaming responses, multi-instance session storage

## API Design

### Context-free endpoints (no session)

```
POST /import          — platform file → Survey JSON
POST /export          — Survey JSON → platform file (download)
POST /create          — Survey JSON → platform API push or file download
```

Always stateless. Suitable for batch scripts, LimeSurvey plugins, custom admin tools.

### Context-aware tool endpoints (session optional)

```
POST /suggest         — question → suggested phrasings + reasoning
POST /validate        — question or survey → list of issues
POST /tag             — question → suggested tags
```

Behaviour with and without `session_id`:

| Endpoint | Without session_id | With session_id |
|---|---|---|
| `/suggest` | Generic single-question reasoning | Loads draft survey; survey-aware suggestions |
| `/validate` | Deterministic checks only | Deterministic + LLM checks; cross-question issues |
| `/tag` | Infers tags from question text | Loads tag vocabulary; prefers reuse; updates vocabulary |

### Conversational API (always session-scoped)

```
POST   /chat/sessions              — create session; returns session_id
GET    /chat/sessions              — list user's active sessions
GET    /chat/{session_id}          — get session metadata + style profile
POST   /chat/{session_id}          — send message; LLM responds + updates draft survey
GET    /chat/{session_id}/survey   — get current draft Survey
POST   /chat/{session_id}/reset    — clear draft + tag vocabulary; keep conversation + docs
DELETE /chat/{session_id}          — terminate session; wipe all files

GET    /chat/{session_id}/style              — get style profile
PUT    /chat/{session_id}/style              — update language / free_text
POST   /chat/{session_id}/style/upload       — upload style guide document

POST   /chat/{session_id}/upload             — upload content document for question generation
```

### LLM Orchestration (server-side)

On each `POST /chat/{session_id}` turn:
1. Load conversation history, draft survey (compact summary), style profile, tag vocabulary
2. Build LLM prompt: system context (style + survey summary) + full conversation history + user message
3. LLM may invoke internal tool calls (suggest, validate, tag) — executed server-side
4. If LLM proposes survey changes, update `draft_survey.json`
5. Append user message + assistant response to `conversation.json`
6. Return `{ "message": "...", "survey_updated": bool }`

The client (m_chat_ui) sends one message and receives one response. No client-side tool execution.

## Adapter `create` Capability

New capability string: `"create"`. All adapters expose it; return value semantics differ:

| Adapter | Implementation | Return value |
|---|---|---|
| LimeSurvey | RemoteControl 2: `add_survey` + `add_group` + `add_question` per item | Platform survey ID (sid) |
| Qualtrics | API v3 `POST /surveys` | Qualtrics survey ID (e.g. `SV_xxx`) |
| SurveyMonkey | No write API on free/standard plan | Serialized file content (fallback) |
| QTI | No platform API | QTI XML file content (fallback) |

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| LimeSurvey create API is complex (one call per question) | Implement iteratively: survey shell → groups → questions; integration test with mock RC2 API |
| LLM context grows large over long conversations | Summarise older conversation turns beyond last N messages; keep full recent history |
| Session_id optional on tool endpoints adds branching complexity | Clean helper: `get_session_context(session_id) -> SessionContext | None` used in all three endpoints |
