# Cue Integration Guide

This guide explains how to integrate Cue with institutional authentication systems and test the API during development.

> For Shape API, see [SHAPE_API.md](SHAPE_API.md).

## Table of Contents

- [Deployment](#deployment)
- [Authentication Model](#authentication-model)
- [JWT Requirements](#jwt-requirements)
- [API Token Endpoint](#api-token-endpoint)
- [OIDC Login](#oidc-login)
- [Session Lifecycle](#session-lifecycle)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
---

## Deployment

Cue API runs on port `8001`. Interactive docs at `http://localhost:8001/docs`.

For setup, Docker Compose instructions, environment variables, and production hardening, see [DEPLOYMENT.md](DEPLOYMENT.md).

**Quick verify:**

```bash
curl http://localhost:8001/health
# {"status":"healthy"}
```

---

## Authentication Model

Cue uses a **federated authentication** approach with two options:

- **OIDC login** (recommended): Built-in `/auth/login` and `/auth/callback` endpoints work with any OIDC provider — Keycloak, Azure AD, Google, institutional eduGAIN/SAML bridges, etc. See [OIDC Login](#oidc-login) below.
- **Pre-issued JWT**: Your existing IdP can issue tokens directly (see [JWT Requirements](#jwt-requirements)).
- **API token** (`POST /auth/token`): Server-to-server and automated access using a shared `API_SECRET` — works in all environments and supports anonymous callers via a caller-supplied `user_id`.

### Key Principles

1. **Token-based**: All API requests require a valid JWT in the `Authorization` header
2. **User-scoped sessions**: Sessions are grouped per user — same user across devices sees the same sessions
3. **Explicit session selection**: OIDC login issues a session-less JWT (`session_id=null`); users must create or resume a session before accessing session-scoped endpoints
4. **Time-limited**: Tokens expire after 24 hours (configurable)

---

## JWT Requirements

### Required Claims

Your institutional IdP must include these claims in issued JWT tokens:

```json
{
  "user_id": "unique_user_identifier",
  "session_id": "stable_session_identifier_or_null",
  "org": "organization_identifier",
  "roles": ["respondent"],
  "iat": 1705132800,
  "exp": 1705219200
}
```

| Claim        | Type           | Description                                                              |
| ------------ | -------------- | ------------------------------------------------------------------------ |
| `user_id`    | string         | Unique, stable user identifier (e.g., email, employee ID)                |
| `session_id` | string \| null | Session identifier, or `null` for session-list-only tokens               |
| `org`        | string         | Organization/tenant identifier for multi-tenant deployments              |
| `roles`      | array          | User roles (currently supports `["respondent"]` for survey participants) |
| `iat`        | timestamp      | Token issued-at time (Unix timestamp)                                    |
| `exp`        | timestamp      | Token expiration time (Unix timestamp)                                   |

> **Session-less tokens** (`session_id=null`) are issued by OIDC login. They can only access session management endpoints (`GET /sessions`, `POST /sessions/new`, `POST /sessions/{id}/select`). All other endpoints require a session-scoped token.

### Token Format

- **Algorithm**: HS256 (HMAC-SHA256)
- **Encoding**: JWT standard (header.payload.signature)
- **Secret**: Shared secret configured via `JWT_SECRET` environment variable

### Example Token Generation (Python)

```python
import jwt
from datetime import datetime, timedelta, timezone

def create_institutional_token(user_id: str, org: str) -> str:
    secret = "your_jwt_secret"  # Same as Cue's JWT_SECRET

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    payload = {
        "user_id": user_id,
        "session_id": f"session_{user_id}_{int(now.timestamp())}",
        "org": org,
        "roles": ["respondent"],
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(payload, secret, algorithm="HS256")
```

---

## API Token Endpoint

### Using the `/auth/token` Endpoint

`POST /auth/token` issues a JWT to any caller that presents a valid API secret. It
is available in **all environments** (development and production) and is the recommended
way to authenticate automated scripts, server-to-server integrations, and anonymous API
consumers.

In multi-tenant deployments, each tenant has its own API secret. The endpoint matches the
secret against the tenant registry first, then falls back to the global `API_SECRET`. The
resulting JWT `org` claim determines which tenant's LLM credentials are used for
subsequent requests. See [DEPLOYMENT.md § Multi-Tenant Setup](DEPLOYMENT.md#multi-tenant-setup).

> **Anonymous callers**: supply any stable unique string as `user_id` (e.g. a UUID or
> HMAC-hash of an internal user identifier). The resulting session is fully isolated.

#### Generate a Token

```bash
curl -X POST http://localhost:8001/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "api_secret": "your-shared-api-secret"
  }'
```

To resume an existing session, include the optional `session_id` field:

```bash
curl -X POST http://localhost:8001/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "api_secret": "your-shared-api-secret",
    "session_id": "a1b2c3d4e5f6"
  }'
```

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "test_user"
}
```

| Field | Required | Description |
|---|---|---|
| `user_id` | yes | Unique user identifier (max 200 chars) |
| `api_secret` | yes | Shared API secret or tenant secret |
| `session_id` | no | Resume an existing session; returns 404 if not found |

Without `session_id`, a new session is created automatically and the JWT includes it.
The endpoint is rate-limited to **10 requests per minute**. An incorrect or absent
`api_secret` returns HTTP 401.

#### Use the Token

```bash
# Save token to variable
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Upload document
curl -X POST http://localhost:8001/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf"

# Get session stats
curl -X GET http://localhost:8001/session/stats \
  -H "Authorization: Bearer $TOKEN"
```

### Environment Configuration

Add to your `.env` file:

```bash
JWT_SECRET=your_secret_key_here
JWT_EXPIRATION_HOURS=24
API_SECRET=your-shared-api-secret   # Required for POST /auth/token
```

---

## OIDC Login

Cue includes built-in OIDC support. Any standard OIDC provider works: Keycloak (bundled), Azure AD, Google, institutional eduGAIN bridges, etc.

### How It Works

```
Browser                Cue             OIDC Provider
  │                       │                        │
  │  GET /auth/login       │                        │
  ├──────────────────────>│                        │
  │                       │  fetch discovery doc   │
  │                       ├──────────────────────>│
  │  302 → provider login │                        │
  │<──────────────────────┤                        │
  │                       │                        │
  │  user logs in         │                        │
  ├──────────────────────────────────────────────>│
  │                       │                        │
  │  redirect to /auth/callback?code=...&state=...│
  │<──────────────────────────────────────────────┤
  │                       │                        │
  │  GET /auth/callback   │                        │
  ├──────────────────────>│                        │
  │                       │  POST /token (code)    │
  │                       ├──────────────────────>│
  │                       │  id_token             │
  │                       │<──────────────────────┤
  │                       │  validate, extract sub│
  │  JWT (session_id=null)│                        │
  │<──────────────────────┤                        │
  │                       │                        │
  │  → /sessions (list)   │                        │
  │  POST /sessions/new   │                        │
  ├──────────────────────>│                        │
  │  JWT (session_id=xxx) │                        │
  │<──────────────────────┤                        │
```

After OIDC login, the JWT has `session_id=null`. The Cue UI redirects to the
session list page where the user creates a new session or resumes an existing one.
Session management endpoints (`/sessions/*`) issue a new JWT with a `session_id`
claim, which is then used for all subsequent API calls.

### Quick Start with Bundled Keycloak

```bash
# 1. Start services (Keycloak auto-imports the expats realm)
docker-compose up

# 2. Set OIDC env vars
OIDC_ISSUER_URL=http://localhost:8080/realms/expats
OIDC_CLIENT_ID=cue-api
OIDC_CLIENT_SECRET=change-me
OIDC_REDIRECT_URI=http://localhost:8001/auth/callback

# 3. Open login URL in browser
open http://localhost:8001/auth/login
# → redirected to Keycloak login
# → after login, JWT with session_id=null is issued
# → UI redirects to session list page

# 4. Create a session and use the token
# (The Cue UI handles this automatically via the session list page)
# For API usage, create a session explicitly:
curl -X POST http://localhost:8001/sessions/new \
  -H "Authorization: Bearer <login-token>"
# → returns { "token": "...", "session_id": "..." }

# 5. Use the session-scoped JWT
curl http://localhost:8001/session/stats \
  -H "Authorization: Bearer <session-token>"
```

See `docs/KEYCLOAK_SETUP.md` for federation (Google, Microsoft, LDAP) and production hardening.

### Connecting a Different OIDC Provider

Set the four env vars to your provider's values:

| Variable | Description |
|---|---|
| `OIDC_ISSUER_URL` | Issuer URL — discovery doc lives at `<issuer>/.well-known/openid-configuration` |
| `OIDC_CLIENT_ID` | Client / app ID registered with the provider |
| `OIDC_CLIENT_SECRET` | Client secret (confidential client) |
| `OIDC_REDIRECT_URI` | Must match the URI registered with the provider; default: `http://localhost:8001/auth/callback` |

### Pre-Issued JWT (Advanced)

If your institution issues JWTs directly (without OIDC redirect flow), the token must contain:

| Claim | Type | Description |
| ------------ | --------- | ----------- |
| `user_id` | string | Unique, stable user identifier |
| `session_id` | string | Session identifier |
| `org` | string | Organization/tenant identifier |
| `roles` | array | e.g. `["respondent"]` |
| `iat` / `exp` | timestamp | Standard JWT timing claims |

The token must be signed with the same `JWT_SECRET` configured in Cue.

---

## Session Lifecycle

### Session Creation

Sessions are **explicitly created** by the user (not auto-created on first request):

1. User authenticates with IdP (OIDC) and receives JWT with `session_id=null`
2. User is redirected to the session list page (`GET /sessions`)
3. User creates a new session (`POST /sessions/new`) or resumes an existing one (`POST /sessions/{id}/select`)
4. A new JWT is issued with the `session_id` claim populated
5. Session folder created: `data/sessions/{user_hash}/{session_id}/`

For API token users (`POST /auth/token`), a session is created automatically when no `session_id` is provided (backward-compatible).

### Session Expiration

- **TTL-based**: Sessions expire after configured hours (default: 24)
- **Automatic cleanup**: Background job removes expired sessions and prunes empty user directories
- **User-initiated**: Users can delete sessions immediately via `DELETE /session`

### Session Storage

Sessions are stored under user-scoped directories. Each user's sessions are isolated by a hash of their `user_id`:

```
data/sessions/
├── a1b2c3d4e5f6g7h8/             # sha256(user_id)[:16]
│   ├── f47ac10b58cc/              # session_id (UUID)
│   │   ├── metadata.json          # Session info (created_at, expires_at, user_id)
│   │   ├── survey.json            # Imported survey
│   │   ├── answer_report.json     # Generated answers (JSONL)
│   │   ├── review_state.json      # User review decisions
│   │   ├── cached_suggestions.json # Suggestion cache for instant reload
│   │   ├── audit_log.json         # Audit trail
│   │   ├── chroma_xxxxxxxx/       # Vector embeddings (ChromaDB)
│   │   └── uploads/               # Uploaded documents
│   └── 9c3e7a1b2d4f/              # Another session for the same user
│       └── ...
└── x9y8z7w6v5u4t3s2/              # Another user
    └── ...
```

This layout enables cross-device session resume (same user, different device), multiple concurrent sessions per user, and GDPR-compliant data deletion (`rm -rf data/sessions/{user_hash}/`).

---

## API Endpoints

### Authentication Required

All endpoints except `/`, `/health`, `/privacy`, `/auth/token`, `/auth/login`, and `/auth/callback` require authentication. Session management endpoints (`/sessions/*`) work with session-less tokens; all others require a session-scoped token.

| Endpoint | Method | Description |
|---|---|---|
| `/sessions` | GET | List all active sessions for the authenticated user |
| `/sessions/new` | POST | Create a new session; returns JWT with session_id |
| `/sessions/{id}/select` | POST | Resume an existing session; returns JWT with session_id |
| `/sessions/{id}/transfer` | POST | Transfer session ownership to another user |
| `/upload` | POST | Upload evidence document (PDF, DOCX, TXT, MD, PPTX, XLSX, XLS, JPG, JPEG, PNG, GIF, WEBP) |
| `/suggest/batch` | POST | Answer suggestions (single or multi-question) from QTI-inspired JSON payload |
| `/suggest/stream` | POST | Same as `/suggest/batch` but streams results via Server-Sent Events — one `event: suggestion` per item as it completes, then `event: done` |
| `/review-state/{question_id}` | PUT | Save review decision (accepted/dismissed/edited) for a single question |
| `/review-state` | GET | Load full review state map for the session |
| `/cached-suggestions` | GET | Retrieve cached suggestion results for instant page reload |
| `/answer-report/download` | GET | Download answer report as JSON (includes review state when available) |
| `/session/stats` | GET | Session TTL, document count, isolation info |
| `/audit-report` | GET | Full session audit trail (JSON or plaintext) |
| `/session` | DELETE | Delete session and all associated data immediately |

#### List Sessions

```bash
GET /sessions
Authorization: Bearer <token>
```

Returns all active (non-expired) sessions for the authenticated user. Works with session-less tokens.

**Response:**

```json
{
  "sessions": [
    {
      "session_id": "f47ac10b58cc",
      "created_at": "2026-05-10T09:00:00",
      "expires_at": "2026-05-11T09:00:00",
      "remaining_hours": 18.5,
      "has_survey": true
    }
  ]
}
```

#### Create New Session

```bash
POST /sessions/new
Authorization: Bearer <token>
```

Creates a new session for the authenticated user and returns a session-scoped JWT.

**Response** (201):

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "session_id": "a1b2c3d4e5f6"
}
```

#### Select / Resume Session

```bash
POST /sessions/{session_id}/select
Authorization: Bearer <token>
```

Resume an existing session. Returns a new JWT scoped to that session. Returns 404 if the session does not exist or does not belong to the caller.

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "session_id": "f47ac10b58cc"
}
```

#### Transfer Session

```bash
POST /sessions/{session_id}/transfer
Authorization: Bearer <token>
Content-Type: application/json

{
  "recipient_user_id": "localhost:8080:other-user-sub"
}
```

Transfers ownership of a session to another user. The recipient must have logged in at least once (their user directory must exist). After transfer, the caller's JWT is no longer valid for this session.

**Response:**

```json
{
  "status": "transferred",
  "session_id": "f47ac10b58cc"
}
```

Returns 404 if the session doesn't exist, isn't owned by the caller, or the recipient hasn't logged in.

#### Upload Document

```bash
POST /upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <document.pdf>
```

#### Get Answer Suggestions

Submit one or more questions in a single request. Use a flat `items` list for a single question, or group related questions into `sections` to share context. Questions in the same section share LLM context, improving suggestion quality.

> **Migrating from the old `POST /suggest` endpoint?** Pass a flat `items` list with one item — the response is in `responses[0]`.

```bash
POST /suggest/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "assessment_id": "gdpr-survey-2026",
  "context": "Annual GDPR compliance questionnaire for EU research institutions",
  "sections": [
    {
      "id": "sec-retention",
      "title": "Data Retention",
      "items": [
        {
          "id": "q1",
          "type": "open_ended",
          "prompt": "Describe your organisation's data retention policy for personal data."
        },
        {
          "id": "q2",
          "type": "single_choice",
          "prompt": "Do you conduct annual GDPR compliance audits?",
          "choices": [
            { "id": "yes",     "label": "Yes"       },
            { "id": "no",      "label": "No"        },
            { "id": "partial", "label": "Partially" }
          ]
        }
      ]
    }
  ]
}
```

A flat `items` list (no `sections`) is also accepted — items are treated as a single implicit section:

```json
{
  "assessment_id": "quick-check",
  "items": [
    { "id": "q1", "type": "open_ended", "prompt": "What is your data retention period?" }
  ]
}
```

**Response:**

```json
{
  "assessment_id": "gdpr-survey-2026",
  "session_id": "sess_abc123",
  "generated_at": "2026-02-24T10:00:00Z",
  "model": "anthropic/claude-haiku-4.5",
  "responses": [
    {
      "item_id": "q1",
      "type": "open_ended",
      "suggestion": "Personal data is retained for 36 months following contract termination, then securely deleted.",
      "selected_id": null,
      "selected_ids": null,
      "reasoning": null,
      "citations": [
        {
          "source": "data_policy_2024.pdf",
          "excerpt": "Personal data shall be retained for no longer than 36 months from contract termination.",
          "position": 0.23
        }
      ]
    },
    {
      "item_id": "q2",
      "type": "single_choice",
      "suggestion": "Partially",
      "selected_id": "partial",
      "selected_ids": null,
      "reasoning": "The documents mention an internal privacy review but do not confirm a formal annual audit.",
      "citations": [
        {
          "source": "annual_report_2025.pdf",
          "excerpt": "An internal privacy review was completed in Q3 2025.",
          "position": 0.67
        }
      ]
    }
  ]
}
```

**Response field reference:**

| Field | Type | Notes |
|---|---|---|
| `suggestion` | string | Human-readable answer, always present, safe to display |
| `selected_id` | string \| null | Matched choice id for `single_choice`; null if uncertain |
| `selected_ids` | list \| null | Matched choice ids for `multiple_choice`; null if uncertain |
| `reasoning` | string \| null | LLM explanation of confidence or uncertainty; null if straightforward |
| `citations[].position` | float | Normalised document position (0.0–1.0) |

> **Input format** is inspired by [QTI 3.0](https://www.imsglobal.org/spec/qti/v3p0/impl) (IMS Global). Supported types: `open_ended`, `single_choice`, `multiple_choice`, `ranking`, `slider`. See `openspec/specs/interchange-formats/` for full standards alignment documentation.

#### Stream Batch Answer Suggestions

Accepts the same request body as `/suggest/batch` but returns results progressively via [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events). One `event: suggestion` is emitted as soon as each item's LLM call completes, followed by a final `event: done`. This avoids browser timeouts for large surveys and lets the UI render suggestions question-by-question.

```bash
POST /suggest/stream
Authorization: Bearer <token>
Content-Type: application/json

{ ...same body as /suggest/batch... }
```

**Response** (`Content-Type: text/event-stream`):

```
event: suggestion
data: {"item_id":"q1","type":"open_ended","suggestion":"Personal data is retained for 36 months...","selected_id":null,"selected_ids":null,"reasoning":null,"citations":[...]}

event: suggestion
data: {"item_id":"q2","type":"single_choice","suggestion":"Partially","selected_id":"partial",...}

event: done
data: {}
```

On error, an `event: error` is emitted with a JSON `{"detail": "..."}` payload instead of `event: done`.

The answer report is persisted to `answer_report.json` after all items have been streamed, identical to the batch endpoint.

#### Query Rewriting

Before vector search, Cue can optionally rewrite survey questions into concise search queries using the LLM. This improves retrieval by stripping verbose framing and extracting key terms — for example, *"Could you please describe your current employment status and the nature of your work arrangement?"* becomes *"employment status work arrangement"*.

Rewriting is **enabled by default** and runs once per section (batching all questions in a single LLM call). It uses available context — question type, answer choices (for choice questions), section title, and uploaded document filenames — to produce targeted search queries.

If the rewrite call fails for any reason, the pipeline silently falls back to the original question text.

| Variable | Default | Description |
|---|---|---|
| `CUE_QUERY_REWRITE` | `true` | Set to `false` to disable query rewriting |
| `CUE_REWRITE_BATCH_SIZE` | `20` | Max questions rewritten per LLM call; larger sections are split |
| `CUE_REWRITE_MODEL` | _(unset)_ | Dedicated model for rewriting (e.g. `google/gemini-2.0-flash-001`); falls back to `DEFAULT_LLM_MODEL` when unset |

The rewritten query is logged in the audit trail alongside each suggestion for pilot diagnostics.

#### Review State

The review state endpoints persist the respondent's per-question review decisions
(accepted, dismissed, edited) server-side. The Cue UI writes to these endpoints on
every interaction and reads the full state on page load. Review state is stored as
`review_state.json` in the session directory and is deleted with the session.

```bash
PUT /review-state/{question_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "state": "accepted",
  "value": "36 months"
}
```

The `state` field is required (`accepted`, `dismissed`, or `edited`). Optional fields:
`value` (text answer), `selected_id` (single choice), `selected_ids` (multiple choice).

```bash
GET /review-state
Authorization: Bearer <token>
```

**Response:**

```json
{
  "states": {
    "q1": { "state": "accepted", "value": "36 months" },
    "q2": { "state": "dismissed" }
  }
}
```

Returns `{"states": {}}` if no review actions have been taken.

#### Cached Suggestions

Suggestions are cached to `cached_suggestions.json` as they are generated (both batch
and streaming). On page reload, the UI fetches the cache and renders previously generated
suggestions instantly — only uncached questions trigger a new SSE stream.

```bash
GET /cached-suggestions
Authorization: Bearer <token>
```

**Response:**

```json
{
  "suggestions": {
    "q1": {
      "item_id": "q1",
      "type": "open_ended",
      "suggestion": "36 months.",
      "reasoning": "Policy document states this.",
      "selected_id": null,
      "selected_ids": null,
      "citations": [...]
    }
  }
}
```

Returns `{"suggestions": {}}` if no suggestions have been generated yet.

#### Download Answer Report

```bash
GET /answer-report/download
Authorization: Bearer <token>
```

Returns the session's answer report as a downloadable JSON array. Each entry contains
the question, suggested answer, reasoning, and citations. When review state exists,
entries are enriched with `review_state` and `final_value` fields:

```json
[
  {
    "question_id": "q1",
    "question": "What is your data retention period?",
    "answer": "36 months.",
    "reasoning": "Policy document states this.",
    "citations": [{"source": "policy.pdf", "position": 0.45, "excerpt": "..."}],
    "generated_at": "2026-05-07T12:00:00Z",
    "review_state": "accepted",
    "final_value": "36 months."
  }
]
```

Returns 404 if no suggestions have been generated yet. The `review_state` and
`final_value` fields are only present for questions with a review decision.

#### Get Session Statistics

```bash
GET /session/stats
Authorization: Bearer <token>
```

**Response:**

```json
{
  "session_id": "sess_abc123",
  "user_id": "john.doe@edu",
  "created_at": "2026-01-13T10:00:00Z",
  "expires_at": "2026-01-14T10:00:00Z",
  "remaining_hours": 22.5,
  "is_expired": false,
  "document_count": 3,
  "isolation_scope": "user"
}
```

#### Download Audit Report

```bash
GET /audit-report
Authorization: Bearer <token>
```

#### Delete Session

```bash
DELETE /session
Authorization: Bearer <token>
```

---

## Troubleshooting

### "Missing or invalid authorization header"

**Cause**: Token not provided or malformed

**Solution**:

```bash
# Ensure Authorization header is present
curl -H "Authorization: Bearer <token>" ...

# Check token format (should be: Bearer <jwt>)
```

### "Token has expired"

**Cause**: JWT `exp` claim is in the past

**Solution**: Generate a new token

```bash
# Via API token endpoint (all environments)
curl -X POST http://localhost:8001/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "your_user", "api_secret": "your-shared-api-secret"}'

# Or via OIDC login for browser-based flows
```

### "Invalid token signature"

**Cause**: JWT_SECRET mismatch between IdP and Cue

**Solution**:

1. Verify `JWT_SECRET` matches in both systems
2. Ensure algorithm is HS256
3. Check token was generated with correct secret

### "No active session" (403)

**Cause**: JWT has `session_id=null` (session-less token) but the endpoint requires an active session

**Solution**: Create or select a session first:

- `POST /sessions/new` to create a new session
- `POST /sessions/{id}/select` to resume an existing one
- The returned JWT includes a `session_id` — use it for subsequent requests

### "Session not found" (404)

**Cause**: Session expired, was deleted, or doesn't belong to the caller

**Solution**:

- List available sessions: `GET /sessions`
- Check session stats: `GET /session/stats`
- Verify JWT contains a valid `session_id`

### "Invalid API secret"

**Cause**: `api_secret` in the `POST /auth/token` request does not match the server's `API_SECRET` env var

**Solution**:

1. Verify `API_SECRET` is set in the server's `.env`
2. Ensure the value in your request matches exactly (case-sensitive)
3. Restart the service after changing `API_SECRET`

### Session Data Missing

**Cause**: Session expired and cleaned up

**Solution**:

- Check `remaining_hours` in session stats
- Configure longer TTL: `SESSION_TTL_HOURS=48`
- Download audit report before session expires

---

## Security Best Practices

See [DEPLOYMENT.md — Production Hardening](DEPLOYMENT.md#production-hardening) for full guidance on secret management, HTTPS, and rate limiting.

---

## Support

- **Technical Issues**: Open issue on GitHub repository
- **Integration Questions**: Contact project maintainers
- **Security Concerns**: Report privately to smartict@pxl.be

---

**Last Updated**: May 2026
**Version**: 0.3.0 (User-scoped sessions, streaming batch suggestions)
