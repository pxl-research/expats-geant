# Cue Integration Guide

This guide explains how to integrate Cue with institutional authentication systems and test the API during development.

> For Shape API, see [MCHAT_API.md](MCHAT_API.md).

## Table of Contents

- [Deployment](#deployment)
- [Authentication Model](#authentication-model)
- [JWT Requirements](#jwt-requirements)
- [API Token Endpoint](#api-token-endpoint)
- [Institutional Integration](#institutional-integration)
- [Session Lifecycle](#session-lifecycle)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
---

## Deployment

The recommended way to run Cue is via Docker Compose.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- An [OpenRouter](https://openrouter.ai) API key (required for suggestion endpoints)

### 1. Create a `.env` file

Create a `.env` file in the project root. This file is read automatically by Docker Compose and is **never committed to version control**.

```bash
# .env

# Required: LLM API key for suggestion endpoints
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Required: Secret used to sign and verify JWT tokens
JWT_SECRET=change-me-to-a-strong-random-secret

# Optional overrides (defaults shown)
LLM_MODEL=openrouter/meta-llama/llama-3.1-8b-instruct
SESSION_TTL_HOURS=24
MAX_FILE_SIZE_MB=50
AUDIT_RETENTION_DAYS=365
LOG_LEVEL=INFO
```

> **Security**: Use a strong random value for `JWT_SECRET` in production (256+ bits of entropy). It must match the secret used by your identity provider to sign tokens.

### 2. Build the image

```bash
docker build -t cue-api:latest .
```

### 3. Start the service

```bash
docker-compose up
```

The service starts on port `8001`. You should see:

```
✓ SessionManager initialized (base: /app/data/sessions)
✓ LLM client initialized
✓ AuditLogger initialized
✓ FastAPI app configured

Starting server on 0.0.0.0:8001...
API docs available at: http://0.0.0.0:8001/docs
```

> **Note**: You may see a harmless `onnxruntime cpuid_info warning: Unknown CPU vendor` message on startup. This is a CPU detection quirk inside the container and does not affect functionality.

### 4. Verify the service is running

```bash
curl http://localhost:8001/health
# {"status":"healthy"}
```

Interactive API documentation is available at: `http://localhost:8001/docs`

### 5. Stop the service

```bash
docker-compose down
```

### Data Persistence

Session data and vector embeddings are stored in named Docker volumes (`sessions_data`, `chroma_data`) and persist across container restarts. To wipe all data:

```bash
docker-compose down -v
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes* | — | API key for LLM calls via OpenRouter |
| `JWT_SECRET` | Yes | `change-me-in-production` | Secret for JWT signing/verification |
| `API_SECRET` | Yes† | — | Shared secret for `POST /auth/token` (server-to-server auth) |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_HOURS` | No | `24` | Token lifetime in hours |
| `LLM_MODEL` | No | `openrouter/meta-llama/llama-3.1-8b-instruct` | LLM model identifier |
| `SESSION_TTL_HOURS` | No | `24` | Session expiry in hours |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum upload file size |
| `AUDIT_RETENTION_DAYS` | No | `365` | Audit log retention period |
| `THINKING_BUDGET_TOKENS` | No | — | Token budget for extended thinking (Claude 3.5+/4.x only) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

†`API_SECRET` is required if you use `POST /auth/token`. Leave unset to disable the endpoint.

*The service starts without an LLM key but suggestion endpoints will return errors.

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

`POST /auth/token` issues a JWT to any caller that presents the shared `API_SECRET`. It
is available in **all environments** (development and production) and is the recommended
way to authenticate automated scripts, server-to-server integrations, and anonymous API
consumers.

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

The endpoint is rate-limited to **5 requests per minute**. An incorrect or absent
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
| `/suggest` | POST | Single-question answer suggestion with citations and reasoning |
| `/suggest/batch` | POST | Multi-question batch suggestions from QTI-inspired JSON payload |
| `/suggest/stream` | POST | Same as `/suggest/batch` but streams results via Server-Sent Events — one `event: suggestion` per item as it completes, then `event: done` |
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

#### Get Answer Suggestion

```bash
POST /suggest
Authorization: Bearer <token>
Content-Type: application/json

{
  "question": "What is my current employment status?",
  "context": "As of 2024"
}
```

**Response:**

```json
{
  "answer": "Based on your contract, you are employed full-time as a Senior Researcher.",
  "reasoning": "The employment contract clearly states the position and contract type. No ambiguity found.",
  "citations": [
    {
      "source": "employment_contract.pdf",
      "excerpt": "Employee is engaged on a full-time permanent basis as Senior Researcher.",
      "position": "23.0%",
      "position_range": { "start_percentage": 0.21, "end_percentage": 0.25 },
      "timestamp": "2026-02-24T10:00:00Z"
    }
  ],
  "metadata": { "num_chunks": 3, "temperature": 0.4 }
}
```

> **`reasoning`**: Optional field — the LLM explains its confidence, how it interpreted the sources, or why it is uncertain. Present on all suggest responses; `null` when the answer is straightforward.

#### Get Batch Answer Suggestions

Submit multiple related questions in one request. Questions grouped in the same section share context, improving suggestion quality.

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

### JWT Secret Management

- **Never commit** `JWT_SECRET` to version control
- Use **strong secrets**: 256+ bits of entropy
- **Rotate secrets** periodically (requires coordination with IdP)
- Use environment-specific secrets (dev ≠ production)

### Token Expiration

- Keep token lifetime **short** (≤24 hours)
- Implement token refresh flow in production
- Validate `exp` claim on every request

### HTTPS in Production

- **Always use HTTPS** for production deployments
- Tokens transmitted over HTTP are vulnerable to interception
- Configure TLS termination at reverse proxy (nginx, Apache)

### Rate Limiting

Consider adding rate limiting for production:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

---

## Support

- **Technical Issues**: Open issue on GitHub repository
- **Integration Questions**: Contact project maintainers
- **Security Concerns**: Report privately to security@institution.edu

---

**Last Updated**: March 2026
**Version**: 0.3.0 (Streaming batch suggestions)
