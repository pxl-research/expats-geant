# Shape API Reference

Shape is the administrator co-pilot for questionnaire design. It provides stateless survey transform endpoints (import/export/create) and AI tool endpoints (suggest/validate/tag), plus a full conversational session API for iterative survey authoring.

> For Cue API, see [CUE_API.md](CUE_API.md).

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Stateless Transform Endpoints](#stateless-transform-endpoints)
  - [POST /import](#post-import)
  - [POST /export](#post-export)
  - [POST /create](#post-create)
- [Tool Endpoints](#tool-endpoints)
  - [POST /suggest](#post-suggest)
  - [POST /validate](#post-validate)
  - [POST /tag](#post-tag)
- [Conversational Chat API](#conversational-chat-api)
  - [Session Lifecycle](#session-lifecycle)
  - [POST /chat/sessions](#post-chatsessions)
  - [GET /chat/sessions](#get-chatsessions)
  - [POST /chat/sessions/{session_id}/select](#post-chatsessionssession_idselect)
  - [GET /chat/{session_id}](#get-chatsession_id)
  - [POST /chat/{session_id}](#post-chatsession_id)
  - [GET /chat/{session_id}/survey](#get-chatsession_idsurvey)
  - [PUT /chat/{session_id}/survey](#put-chatsession_idsurvey)
  - [Granular survey mutations](#granular-survey-mutations)
  - [GET /chat/{session_id}/messages](#get-chatsession_idmessages)
  - [DELETE /chat/{session_id}](#delete-chatsession_id)
  - [POST /chat/{session_id}/reset](#post-chatsession_idreset)
- [Style Profile](#style-profile)
  - [GET /chat/{session_id}/style](#get-chatsession_idstyle)
  - [PUT /chat/{session_id}/style](#put-chatsession_idstyle)
  - [POST /chat/{session_id}/style/upload](#post-chatsession_idstyleupload)
- [Document Upload](#document-upload)
  - [POST /chat/{session_id}/upload](#post-chatsession_idupload)
- [Session Directory Structure](#session-directory-structure)
- [Troubleshooting](#troubleshooting)

---

## Overview

- **Base URL**: `http://localhost:8003`
- **Interactive docs**: `http://localhost:8003/docs`
- **Service**: `shape-api` (Docker Compose)
- **Port**: `8003`

All endpoints except `/`, `/health`, `/auth/token`, `/auth/login`, and `/auth/callback` require a valid JWT in the `Authorization: Bearer <token>` header.

---

## Authentication

Shape uses the same JWT authentication model as Cue. See [CUE_API.md — Authentication Model](CUE_API.md#authentication-model) and [JWT Requirements](CUE_API.md#jwt-requirements) for full details.

### Quick start

```bash
# 1. Generate a token via the API token endpoint (set API_SECRET in .env first)
TOKEN=$(curl -s -X POST "http://localhost:8001/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"dev_user","api_secret":"your-shared-api-secret"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Use the token
curl http://localhost:8003/chat/sessions \
  -H "Authorization: Bearer $TOKEN"
```

---

## Stateless Transform Endpoints

These endpoints convert surveys between the internal format and platform-specific formats. They require authentication but do **not** need a chat session.

### POST /import

Parse a platform survey file and return the internal `Survey` JSON.

**Supported formats**: `limesurvey` (or `lss`), `qualtrics` (or `qsf`), `surveymonkey` (or `sm`), `qti`

```bash
curl -X POST http://localhost:8003/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "limesurvey",
    "content": "<xml content of LimeSurvey LSS file>"
  }'
```

**Response:**

```json
{
  "survey": {
    "id": "survey_abc",
    "title": "Annual Staff Survey",
    "questions": [...]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `format` | string | Platform format identifier |
| `content` | string | Raw file content (XML, JSON, etc.) |

**Error**: `400` if the content cannot be parsed; `422` if the format is unknown.

---

### POST /export

Serialise an internal `Survey` to a platform-specific format.

```bash
# Export to QTI
curl -X POST http://localhost:8003/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "qti",
    "survey": { "id": "s1", "title": "My Survey", "questions": [] }
  }'

# Export to Qualtrics QSF
curl -X POST http://localhost:8003/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "qualtrics",
    "survey": { "id": "s1", "title": "My Survey", "questions": [] }
  }'
```

**Response:**

```json
{
  "format": "qti",
  "content": "<?xml version=\"1.0\"?>..."
}
```

---

### POST /create

Create a survey on the target platform API, or fall back to file export if credentials are absent or the platform doesn't support direct creation.

```bash
# API create on LimeSurvey (requires credentials)
curl -X POST http://localhost:8003/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "limesurvey",
    "survey": { "id": "s1", "title": "Staff Survey 2026", "questions": [] },
    "api_url": "http://limesurvey.example.com/admin/remotecontrol",
    "username": "admin",
    "password": "secret"
  }'

# File export fallback (no credentials)
curl -X POST http://localhost:8003/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "surveymonkey",
    "survey": { "id": "s1", "title": "Quick Poll", "questions": [] }
  }'
```

**Response:**

```json
{
  "format": "limesurvey",
  "platform_id": "123456",
  "created_via": "api"
}
```

| `created_via` | Meaning |
|---|---|
| `"api"` | Survey created directly via platform API; `platform_id` is the platform's survey ID |
| `"file_export"` | No API credentials provided or platform doesn't support API creation; `platform_id` contains the exported file content |

**Request fields:**

| Field | Required | Description |
|---|---|---|
| `format` | Yes | Platform format |
| `survey` | Yes | Internal Survey JSON |
| `api_url` | No | API base URL (LimeSurvey) or datacenter ID (Qualtrics) |
| `token` | No | API token (Qualtrics) |
| `username` | No | Username (LimeSurvey) |
| `password` | No | Password (LimeSurvey) |

---

## Tool Endpoints

These endpoints apply AI tools to a question or survey. They require authentication. Passing a `session_id` enriches the request with the session's style profile and draft survey context.

### POST /suggest

Generate improved phrasings for a survey question.

```bash
# Without session context
curl -X POST http://localhost:8003/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": {
      "id": "q1",
      "type": "open_ended",
      "text": "How do you feel about your current workload?"
    },
    "n_suggestions": 3
  }'

# With session context (applies style profile)
curl -X POST http://localhost:8003/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": { "id": "q1", "type": "open_ended", "text": "How do you feel about your current workload?" },
    "session_id": "your-session-uuid",
    "n_suggestions": 2
  }'
```

**Response:**

```json
{
  "suggestions": [
    {
      "phrasing": "How would you describe your current workload?",
      "reasoning": "Uses 'describe' for a more structured, neutral response prompt."
    },
    {
      "phrasing": "How manageable is your current workload?",
      "reasoning": "Focuses on the actionable dimension of workload management."
    }
  ]
}
```

**Error**: `500` if LLM client is not configured; `403` if `session_id` is provided but not found or belongs to another user.

---

### POST /validate

Validate a question or full survey for quality issues. Uses Tier 1 deterministic rules (always) and Tier 2 LLM checks (when LLM client is configured).

```bash
# Validate a single question
curl -X POST http://localhost:8003/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": {
      "id": "q1",
      "type": "single_choice",
      "text": "Do you agree or disagree with our policy?"
    }
  }'

# Validate the session draft survey
curl -X POST http://localhost:8003/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-uuid"
  }'
```

**Response:**

```json
{
  "issues": [
    {
      "question_id": "q1",
      "severity": "warning",
      "code": "double_barreled",
      "message": "Question asks about two things at once ('agree or disagree' with a policy)."
    }
  ]
}
```

Issue severity values: `"error"`, `"warning"`, `"info"`.

**Error**: `422` if neither `question`, `survey`, nor a session with a draft survey is provided.

---

### POST /tag

Suggest normalised tags for a survey question. When a `session_id` is provided, new tags are persisted to the session vocabulary.

```bash
curl -X POST http://localhost:8003/tag \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": {
      "id": "q3",
      "type": "multiple_choice",
      "text": "Which data retention policies does your organisation follow?"
    },
    "session_id": "your-session-uuid"
  }'
```

**Response:**

```json
{
  "tags": ["data-retention", "compliance", "gdpr", "policy"],
  "vocabulary_updated": true
}
```

`vocabulary_updated` is `true` when tags were persisted to the session's `tag_vocabulary.json`.

---

## Conversational Chat API

The conversational API supports iterative survey authoring through multi-turn dialogue. The AI can propose survey edits based on natural language instructions, and changes are stored in the session draft.

### Session Lifecycle

```
POST /chat/sessions          ← create session
  │
  ├─ POST /chat/{id}/upload  ← (optional) provide context documents
  ├─ PUT  /chat/{id}/style   ← (optional) set style preferences
  │
  ├─ POST /chat/{id}         ← send message, get AI response
  │    └── survey_updated: true → draft updated in session
  │
  ├─ GET  /chat/{id}/survey   ← retrieve current draft at any time
  ├─ PUT  /chat/{id}/survey   ← replace the whole draft (external editor)
  ├─ POST/PATCH/DELETE /chat/{id}/survey/sections[/{section_id}]              ← granular section edits
  ├─ POST/PATCH/DELETE /chat/{id}/survey/sections/{section_id}/questions      ← granular question edits
  │    and /chat/{id}/survey/questions/{question_id}                             (see "Granular survey mutations")
  ├─ PATCH /chat/{id}/survey/{sections|questions}/{id}/position               ← reorder / move by list position
  │
  ├─ POST /export            ← export draft to target platform
  │
  └─ DELETE /chat/{id}       ← clean up when done
```

The AI edits the draft by calling internal mutation tools (add/update/delete a
section or question), so a chat turn touches only the parts that change rather
than re-emitting the whole survey. Poll `GET /chat/{session_id}/survey` after any
turn where `survey_updated: true`. The same granular mutations are also available
as the REST endpoints documented below, for external editors and integrations.

---

### POST /chat/sessions

Create a new conversational chat session.

```bash
curl -X POST http://localhost:8003/chat/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response** (`201 Created`):

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "dev_user",
  "created_at": "2026-03-12T10:00:00",
  "expires_at": "2026-03-13T10:00:00",
  "style_profile": {
    "language": "en",
    "free_text": "",
    "document_summary": ""
  },
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

The `token` field contains a new JWT scoped to the created session. Use this token for all subsequent API calls on this session.

---

### GET /chat/sessions

List all chat sessions for the authenticated user.

```bash
curl http://localhost:8003/chat/sessions \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "sessions": [
    {
      "session_id": "550e8400-...",
      "user_id": "dev_user",
      "created_at": "2026-03-12T10:00:00",
      "expires_at": "2026-03-13T10:00:00",
      "style_profile": { "language": "en", "free_text": "", "document_summary": "" }
    }
  ]
}
```

---

### POST /chat/sessions/{session_id}/select

Select (resume) an existing chat session. Returns a new JWT scoped to the selected session.

```bash
curl -X POST http://localhost:8003/chat/sessions/550e8400-.../select \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "dev_user",
  "created_at": "2026-03-12T10:00:00",
  "expires_at": "2026-03-13T10:00:00",
  "style_profile": { "language": "en", "free_text": "", "document_summary": "" },
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

Use the returned `token` for all subsequent API calls on this session. The initial token from OIDC login has no session scope — you must create or select a session before accessing session-specific endpoints.

---

### GET /chat/{session_id}

Get metadata for a specific session.

```bash
curl http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $TOKEN"
```

Returns a `ChatSessionResponse` (same shape as `POST /chat/sessions` response).

---

### POST /chat/{session_id}

Send a message and get an AI response. The AI may update the draft survey if the message implies a structural change.

```bash
curl -X POST http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add a question asking about remote work preferences with three options: always, hybrid, office only"
  }'
```

**Response:**

```json
{
  "message": "I've added a single-choice question about remote work preferences with the three options you specified.",
  "survey_updated": true
}
```

When `survey_updated` is `true`, fetch the updated draft via `GET /chat/{session_id}/survey`.

**How the turn works internally.** The server runs a bounded tool-call loop
(max 3 model round-trips per turn). The model sees an ID-anchored summary of
the current draft in its system prompt — types, options, and metadata are
deliberately omitted from the summary. When the model proposes a structural
change, it is instructed to first call the internal `get_full_survey` tool,
which returns the full authoritative draft JSON for the session. The model
then builds its `<survey_update>` from that JSON. This typically adds one
round-trip to edit turns; pure Q&A turns remain a single round-trip and incur
no tool overhead.

---

### GET /chat/{session_id}/survey

Retrieve the current draft survey for a session.

```bash
curl http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/survey \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "survey": {
    "id": "draft_550e8400",
    "title": "Staff Survey Draft",
    "description": "",
    "metadata": {},
    "sections": [
      {
        "id": "sec_1",
        "title": "Work Preferences",
        "description": "",
        "metadata": {},
        "questions": [
          {
            "id": "q_1",
            "text": "What is your preferred work arrangement?",
            "type": "single_choice",
            "required": true,
            "min_value": null,
            "max_value": null,
            "step": null,
            "metadata": {},
            "answer_options": [
              { "id": "opt_1", "text": "Always remote", "value": null },
              { "id": "opt_2", "text": "Hybrid", "value": null },
              { "id": "opt_3", "text": "Office only", "value": null }
            ]
          }
        ]
      }
    ]
  }
}
```

`survey` is `null` if no draft has been created yet. The full schema (Survey →
Section → Question → AnswerOption, with field-level constraints) is exposed in
the auto-generated OpenAPI docs at `/docs` and `/openapi.json`.

---

### PUT /chat/{session_id}/survey

Replace the draft survey with an externally edited version. Use this to sync changes
made in an external editor back to the session, instead of sending the full survey JSON
in a chat message. The endpoint validates the survey schema and returns any
methodological quality issues.

```bash
curl -X PUT http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/survey \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "survey": {
      "id": "survey_1",
      "title": "Staff Survey",
      "sections": [
        {
          "id": "sec_1",
          "title": "Work Preferences",
          "description": "",
          "metadata": {},
          "questions": [
            {
              "id": "q_1",
              "text": "What is your preferred work arrangement?",
              "type": "single_choice",
              "required": true,
              "answer_options": [
                {"id": "opt_1", "text": "Remote"},
                {"id": "opt_2", "text": "Hybrid"},
                {"id": "opt_3", "text": "Office"}
              ],
              "min_value": null,
              "max_value": null,
              "step": null,
              "metadata": {}
            }
          ]
        }
      ],
      "metadata": {}
    }
  }'
```

**Response** (`200 OK`):

```json
{
  "status": "saved",
  "validation_issues": [
    {
      "question_id": "q_1",
      "severity": "warning",
      "code": "scale_too_short",
      "message": "Only 3 option(s) provided; consider at least 4 for a meaningful scale."
    }
  ]
}
```

**Errors:**
- `422` if the survey JSON does not match the required schema (missing fields, invalid question type, etc.). The response body follows FastAPI's standard validation-error format: `{"detail": [{"type": "...", "loc": [...], "msg": "...", "input": ...}, ...]}`.
- `403` if the session does not exist or belongs to another user

**Typical workflow for external editor integration:**
1. `PUT /chat/{id}/survey` to sync your local edits to the server
2. `POST /chat/{id}` with a short instruction (e.g., "improve question 3") — no need to include the survey JSON
3. `GET /chat/{id}/survey` to fetch the AI's updated version back

---

### Granular survey mutations

For surgical edits — without re-sending the whole survey — eight endpoints apply a
single change to the draft. Each shares the same mutation logic the chat AI uses,
and each returns the standard `{"status": "saved", "validation_issues": [...]}`
body (the same shape as `PUT /chat/{session_id}/survey`).

| Method | Path | Body |
|--------|------|------|
| `POST` | `/chat/{session_id}/survey/sections` | `{"section": {...}, "after_id": "sec_1"}` |
| `PATCH` | `/chat/{session_id}/survey/sections/{section_id}` | `{"title": "...", "description": "...", "metadata": {}}` |
| `DELETE` | `/chat/{session_id}/survey/sections/{section_id}` | — |
| `PATCH` | `/chat/{session_id}/survey/sections/{section_id}/position` | `{"after_id": "sec_2"}` |
| `POST` | `/chat/{session_id}/survey/sections/{section_id}/questions` | `{"question": {...}, "after_id": "q_1"}` |
| `PATCH` | `/chat/{session_id}/survey/questions/{question_id}` | `{"text": "...", "type": "...", "answer_options": [...], ...}` |
| `DELETE` | `/chat/{session_id}/survey/questions/{question_id}` | — |
| `PATCH` | `/chat/{session_id}/survey/questions/{question_id}/position` | `{"after_id": "q_2", "section_id": "sec_2"}` |

`after_id` is optional on the add endpoints: the new section/question is inserted
after the named sibling, or appended when omitted. PATCH bodies are partial — only
the fields you include are changed (a `section` PATCH cannot contain `questions`;
manage questions through the question endpoints).

Ordering is determined solely by list position — there is no `order` field. Use the
`/position` endpoints to reorder: `after_id` places the element immediately after the
named sibling, or moves it to the front when omitted. On the question `/position`
endpoint, an optional `section_id` moves the question into a different section,
preserving its id and all other fields.

```bash
curl -X PATCH http://localhost:8003/chat/$SID/survey/questions/q_1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is your preferred working arrangement?"}'
```

**Response** (`200 OK`):

```json
{ "status": "saved", "validation_issues": [] }
```

**Errors:**
- `404` if the referenced `section_id` / `question_id` does not exist
- `409` if an added section/question `id` already exists in the draft
- `400` if no draft exists yet, or the patch is otherwise invalid
- `422` if the request body does not match the schema (FastAPI validation format)
- `403` if the session does not exist or belongs to another user

Note on section size: sections beyond ~30 questions surface a `section_dense`
warning, and beyond ~50 a `section_overlong` warning, in `validation_issues`.
These are advisory only — no hard cap is enforced.

---

### GET /chat/{session_id}/messages

Get the full conversation history.

```bash
curl http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/messages \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "messages": [
    { "role": "user", "content": "Add a question about remote work preferences..." },
    { "role": "assistant", "content": "I've added a single-choice question..." }
  ]
}
```

---

### DELETE /chat/{session_id}

Delete a session and all its data (draft, vocabulary, conversation, documents).

```bash
curl -X DELETE http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{ "deleted": true, "session_id": "550e8400-e29b-41d4-a716-446655440000" }
```

---

### POST /chat/{session_id}/reset

Clear the draft survey and tag vocabulary while preserving conversation history. Useful for starting a new survey design within an existing conversation.

```bash
curl -X POST http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/reset \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "reset": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "cleared": ["draft_survey.json", "tag_vocabulary.json"]
}
```

---

## Style Profile

The style profile influences how the AI phrases suggestions and validates questions. It is stored per session and applied automatically to all tool calls made with that `session_id`.

### GET /chat/{session_id}/style

```bash
curl http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/style \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "style_profile": {
    "language": "en",
    "free_text": "Use plain language. Avoid jargon.",
    "document_summary": ""
  }
}
```

---

### PUT /chat/{session_id}/style

Update language and/or free-text style instructions.

```bash
curl -X PUT http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/style \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "nl",
    "free_text": "Gebruik formele taal. Vermijd vakjargon."
  }'
```

Both fields are optional — omit one to leave it unchanged.

---

### POST /chat/{session_id}/style/upload

Upload a style guide document. The text is extracted and summarised, then stored in `style_profile.document_summary`. Supported formats: `.pdf`, `.docx`, `.txt`, `.md`, `.pptx`.

```bash
curl -X POST http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/style/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@institutional_style_guide.pdf"
```

**Response:**

```json
{
  "filename": "institutional_style_guide.pdf",
  "topic_summary": "The document covers plain-language guidelines, accessibility requirements, and brand tone-of-voice for PXL University surveys.",
  "characters_extracted": 14820
}
```

---

## Document Upload

Upload a content document to give the AI context for chat turns (e.g., an existing survey, policy document, or reference material). Supported formats: `.pdf`, `.docx`, `.txt`, `.md`, `.pptx`.

### POST /chat/{session_id}/upload

```bash
curl -X POST http://localhost:8003/chat/550e8400-e29b-41d4-a716-446655440000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@existing_survey_draft.docx"
```

**Response:**

```json
{
  "filename": "existing_survey_draft.docx",
  "topic_summary": "The document contains a draft GDPR compliance survey with 12 questions covering data retention, access controls, and breach notification.",
  "characters_extracted": 8430
}
```

The extracted text is saved as Markdown in the session's `documents/` directory and included as context in subsequent chat turns.

---

## Session Directory Structure

Each chat session stores its data under the configured `SESSIONS_BASE_PATH`:

```
sessions/
└── {session_id}/
    ├── metadata.json          # Session info (user_id, created_at, expires_at)
    ├── draft_survey.json      # Current survey draft (updated by chat turns)
    ├── tag_vocabulary.json    # Accumulated tag vocabulary for this session
    ├── conversation.json      # Full message history (role + content)
    ├── style_profile.json     # Style profile (language, free_text, document_summary)
    ├── documents/             # Uploaded content documents (as .md after extraction)
    └── style_documents/       # Uploaded style guide documents
```

---

## Troubleshooting

### `403 Forbidden — Session not found or access denied`

**Causes:**
- The `session_id` does not exist (expired or never created)
- The session belongs to a different user

**Fix:** Create a new session with `POST /chat/sessions` or list existing sessions with `GET /chat/sessions`.

### `500 — LLM client not configured`

The `suggest` and `tag` endpoints require `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) to be set. The service starts without an LLM key, but these endpoints will return 500.

**Fix:** Add `OPENROUTER_API_KEY=sk-or-v1-your-key` to `.env` and restart.

### `422 — Unknown format`

Supported format identifiers: `limesurvey`, `lss`, `qualtrics`, `qsf`, `surveymonkey`, `sm`, `qti`.

### `422 — Unsupported file type`

Upload endpoints accept `.pdf`, `.docx`, `.txt`, `.md`, `.pptx` only.

### `401 — Invalid API secret`

The `api_secret` value in your `POST /auth/token` request does not match the server's `API_SECRET` env var, or the env var is not set. Check your `.env` and restart the service.

### Auth errors (expired token, invalid signature)

See [CUE_API.md — Troubleshooting](CUE_API.md#troubleshooting) — the JWT model is identical.

---

**Last Updated**: March 2026
**Version**: 0.1.0
