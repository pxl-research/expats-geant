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
2. **Stateless**: No server-side session storage; JWT contains all auth info
3. **Session-scoped**: Each JWT includes a `session_id` that isolates user data
4. **Time-limited**: Tokens expire after 24 hours (configurable)

---

## JWT Requirements

### Required Claims

Your institutional IdP must include these claims in issued JWT tokens:

```json
{
  "user_id": "unique_user_identifier",
  "session_id": "stable_session_identifier",
  "org": "organization_identifier",
  "roles": ["respondent"],
  "iat": 1705132800,
  "exp": 1705219200
}
```

| Claim        | Type      | Description                                                              |
| ------------ | --------- | ------------------------------------------------------------------------ |
| `user_id`    | string    | Unique, stable user identifier (e.g., email, employee ID)                |
| `session_id` | string    | Session identifier (should be stable across requests in same session)    |
| `org`        | string    | Organization/tenant identifier for multi-tenant deployments              |
| `roles`      | array     | User roles (currently supports `["respondent"]` for survey participants) |
| `iat`        | timestamp | Token issued-at time (Unix timestamp)                                    |
| `exp`        | timestamp | Token expiration time (Unix timestamp)                                   |

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

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "test_user"
}
```

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
  │  { "token": "<jwt>" } │                        │
  │<──────────────────────┤                        │
```

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
# → after login, browser receives { "token": "eyJ..." }

# 4. Use the platform JWT
curl http://localhost:8001/session/stats \
  -H "Authorization: Bearer <token>"
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

Sessions are **automatically created** on first authenticated request:

1. User authenticates with IdP and receives JWT
2. User makes first API request (e.g., `POST /upload`)
3. Cue middleware extracts `session_id` from JWT
4. Session folder created: `sessions/{session_id}/`
5. Session metadata saved with TTL (default: 24 hours)

### Session Expiration

- **TTL-based**: Sessions expire after configured hours (default: 24)
- **Automatic cleanup**: Background job removes expired sessions
- **User-initiated**: Users can delete sessions immediately via `DELETE /session`

### Session Isolation

Each session has isolated storage:

```
sessions/
├── sess_abc123/
│   ├── metadata.json       # Session info (created_at, expires_at)
│   ├── chroma_store/       # Vector embeddings
│   ├── documents/          # Uploaded files
│   └── audit_log.json      # Audit trail
└── sess_xyz789/
    └── ...
```

---

## API Endpoints

### Authentication Required

All endpoints except `/`, `/health`, `/privacy`, `/auth/token`, `/auth/login`, and `/auth/callback` require authentication.

| Endpoint | Method | Description |
|---|---|---|
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
| `CUE_REWRITE_MODEL` | _(unset)_ | Dedicated model for rewriting (e.g. `google/gemini-2.0-flash-001`); falls back to the primary LLM configuration when unset |

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

### "Session not found"

**Cause**: Session expired or never created

**Solution**:

- Check session stats: `GET /session/stats`
- Upload a document to trigger session creation
- Verify JWT contains valid `session_id`

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
- **Security Concerns**: Report privately to security@institution.edu

---

**Last Updated**: March 2026
**Version**: 0.3.0 (Streaming batch suggestions)
