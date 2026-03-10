## Context

M-Chat assists survey administrators in designing questionnaires. The challenge is that useful
assistance requires context: knowing what questions already exist, what tags have been used, and
what the overall survey is trying to achieve. A purely stateless API loses this context; a purely
stateful API is too heavy for institutional integrations.

The solution is a layered architecture: context-free endpoints for integrations, context-aware
endpoints that optionally accept a session, and a full conversational layer for the pilot UI.
Session storage follows the same per-user folder isolation pattern established by M-Autofill.

## Goals / Non-Goals

- **Goals:**
  - Suggestion, validation, and tagging engines grounded in survey design best practices
  - Stateless REST endpoints callable from any institutional tool without session overhead
  - Session-aware versions of the same endpoints for richer, survey-scoped reasoning
  - Conversational chat API for iterative questionnaire authoring
  - Document upload: slide decks / Word docs / PDFs → LLM extracts structure → initial question draft
  - Survey creation via adapter API (LimeSurvey, Qualtrics); file download fallback for others
  - Simple `m_chat_ui/` chat interface for the pilot
- **Non-Goals:**
  - Conditional/branching question logic
  - LLM-based evaluation of suggestion quality (post-PoC)
  - Multi-instance session storage (Redis); single-instance filesystem is sufficient for pilot
  - Streaming responses (SSE/WebSocket) — standard request/response for PoC

## Architecture

### Layer Overview

```
m_chat_ui  ─────────────────────────────────────────────────────────────┐
                                                                         │
           ┌─────────────────────────────────────────────────────────┐   │
           │  Conversational API  (always session-scoped)            │   │
           │  POST /chat/{session_id}                                │◄──┘
           │  GET  /chat/{session_id}/survey                         │
           │  POST /chat/{session_id}/upload                         │
           │  DELETE /chat/{session_id}                              │
           └───────────────────┬─────────────────────────────────────┘
                               │ orchestrates via server-side tool calls
           ┌───────────────────▼─────────────────────────────────────┐
           │  Context-aware tool endpoints  (session_id optional)    │
           │  POST /suggest    POST /validate    POST /tag            │
           └───────────────────┬─────────────────────────────────────┘
                               │ reads/writes session state
           ┌───────────────────▼─────────────────────────────────────┐
           │  Context-free endpoints  (never need a session)         │
           │  POST /import    POST /export    POST /create            │
           └─────────────────────────────────────────────────────────┘
```

### Session Storage Layout

Reuses `m_shared/session/manager.py` for creation, TTL tracking, and cleanup.
Per-session folder structure:

```
sessions/{session_id}/
├── draft_survey.json       # current Survey object; updated on every chat turn
├── tag_vocabulary.json     # { tag: [question_ids] } — built up as questions are tagged
├── style_profile.json      # style settings + language (see below)
├── conversation.json       # chat message history [ {role, content, timestamp} ]
├── documents/              # content documents: source material for question generation
│   └── {filename}.chunks.json
└── style_documents/        # style guide documents: institutional writing guidelines
    └── {filename}.extracted.txt
```

**Style profile** (`style_profile.json`):
```json
{
  "language": "en",
  "free_text": "Formal tone, 5-point scales, non-technical audience.",
  "document_summary": "Extracted summary from uploaded institutional style guide.",
  "defaults_applied": true
}
```
- `language`: ISO 639-1 code (e.g. `"en"`, `"nl"`, `"fr"`); defaults to `"en"`. Passed to
  the LLM on every turn so suggestions, validation feedback, and generated questions are
  all produced in the correct language.
- `free_text`: typed by the admin at session start or updated at any point during the session.
- `document_summary`: extracted and summarised from an uploaded style guide document (PDF,
  DOCX, TXT). Processed via MarkItDown, then the LLM generates a concise summary of the
  style rules found, which is stored here rather than the full text.
- `defaults_applied`: `true` when neither free text nor a document was provided. Defaults
  are English language, neutral formal tone, and the general rules from
  `docs/SURVEY_DESIGN_GUIDELINES.md`.

A **style guide document** and a **content document** both use the same MarkItDown extraction
pipeline but serve different purposes and are stored in different subfolders:
- `style_documents/` — institutional writing guidelines; influences how questions are worded.
- `documents/` — survey topic source material (slide decks, reports); used to generate
  initial question drafts.

**Session lifecycle:**
TTL: 7 days (configurable), longer than M-Autofill's 24–48h because survey design is a
multi-day activity. Sessions are linked to a user (via JWT `user_id`, same as M-Autofill)
and can be resumed at any point within the TTL window. A user may have multiple active
sessions simultaneously (one per survey project). The landing page lists the user's active
sessions so they can resume an existing project or start a new one.

Two termination modes:
- **Terminate** (`DELETE /chat/{session_id}`): wipes all session files; session is gone.
- **Reset draft** (`POST /chat/{session_id}/reset`): clears `draft_survey.json` and
  `tag_vocabulary.json` back to empty, but preserves conversation history, uploaded
  documents, and style profile. Useful when the admin wants to restart the questionnaire
  structure without losing earlier context or style settings.

No audit report needed for M-Chat sessions — the output is the survey itself, exported
by the admin.

### Context-Aware Tool Endpoints

Each of `suggest`, `validate`, `tag` accepts an optional `session_id`:

- **Without session_id**: generic single-question reasoning. No survey context. Suitable for
  one-off institutional API calls.
- **With session_id**: loads `draft_survey.json` and `tag_vocabulary.json` from the session
  folder; passes a compact survey summary as LLM context. Returns richer, survey-aware output.

### Tagging with Session Context

Tag vocabulary consistency is the key reason tagging is session-aware. On each `/tag` call with
a session:
1. Load `tag_vocabulary.json` — the accumulated tag set for this survey
2. Pass existing tags as context to the LLM: "Tags already used: [data-retention, consent, ...]"
3. LLM returns tags for the new question, preferring existing tags where appropriate
4. Update `tag_vocabulary.json` with any new tags introduced

Without a session, the tagger infers tags purely from the question text.

### Conversational API — LLM Orchestration

The `/chat/{session_id}` endpoint uses server-side orchestration: the LLM receives the
conversation history + a compact JSON summary of the current draft survey, then decides whether
to call internal tools (suggest, validate, tag), generate new questions, or just respond.
The client (`m_chat_ui`) sends one message and receives one response — no client-side tool
execution needed. This keeps the UI simple.

LLM context per turn:
```
System: You are a survey design assistant. Current draft: {compact_survey_json}.
        Tag vocabulary: {tag_list}. Style profile: {style_profile}.
Messages: [ ...conversation_history... ]
User: {new_message}
```

### Document Upload Flow

1. Admin uploads a file (PPTX, DOCX, PDF, TXT) to `POST /chat/{session_id}/upload`
2. MarkItDown extracts text (reuses `m_shared/vectordb/utils.py`)
3. Text is chunked and stored in `sessions/{session_id}/documents/`
4. On next chat turn, LLM receives a summary of extracted topics
5. LLM proposes an initial survey structure; admin confirms or adjusts

### Survey Creation via Adapter

New capability string: `"create"`. Behaviour per adapter:

| Adapter | `"create"` behaviour |
|---|---|
| LimeSurvey | POST to RemoteControl 2 API → `add_survey` + `add_group` + `add_question` per question; returns platform survey ID |
| Qualtrics | POST to API v3 `/surveys` → returns Qualtrics survey ID |
| SurveyMonkey | Not supported via API (requires paid plan); falls back to file export |
| QTI | No platform API; returns QTI XML as file download |

The `create_survey(survey: Survey) -> str` method returns the platform survey ID for API-backed
adapters, or a serialized file payload for file-fallback adapters. Callers check
`"create" in adapter.capabilities()` before calling; all adapters expose `"create"` but the
return value semantics differ (ID string vs. file content string).

### m_chat_ui

Minimal HTMX-based chat interface, modelled on `m_ui/`. Key pages:

- `/` — start new session or resume existing; option to upload a source document
- `/session/{session_id}/chat` — conversational interface (message input + response stream)
- `/session/{session_id}/survey` — read-only preview of current draft Survey
- `/session/{session_id}/export` — export/create options (platform selector)

The UI calls only the conversational API; it never calls the tool endpoints directly.

## Decisions

- **Server-side orchestration over client-side tool use**: keeps `m_chat_ui` simple; consistent
  with how `m_ui` works for M-Autofill.
- **Filesystem session storage over in-memory**: consistent with M-Autofill; survives restarts;
  simpler than Redis for single-instance pilot deployment.
- **Optional session_id on tool endpoints**: gives institutional integrators a working path
  without requiring session infrastructure, while enabling full context-aware behaviour for the UI.
- **Reuse MarkItDown + chunking utils**: already proven for PDF/DOCX in M-Autofill; no new
  dependency needed for document upload.
- **Validation rules grounded in SURVEY_DESIGN_GUIDELINES.md**: deterministic rule checks
  (double-barreling, leading language, scale length) run without LLM; LLM used only for
  subjective assessments (clarity, tone).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| LLM context window fills up for long surveys | Pass compact survey summary (question IDs + text only), not full model with metadata |
| Tag vocabulary drift (LLM introduces near-duplicate tags) | Normalize tag strings (lowercase, strip whitespace) before storing; present existing tags prominently in prompt |
| LimeSurvey create API complexity | Implement iteratively: survey shell first, then groups, then questions; integration test with a real LimeSurvey instance |
| m_chat_ui scope creep | Keep it strictly a thin wrapper over the conversational API; no business logic in the UI |

## Open Questions

- **Style profile scope**: For the PoC, a style profile is a free-text field the admin provides
  at session start ("formal tone, 5-point scales, non-technical audience"). The LLM includes it
  as system context on every turn. A more structured per-institution config (persistent across
  sessions, set by an org admin) is a post-pilot consideration. Defer unless pilot feedback
  specifically requests it.
