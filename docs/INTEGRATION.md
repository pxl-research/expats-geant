# M-Autofill Integration Guide

This guide explains how to integrate M-Autofill with institutional authentication systems and test the API during development.

## Table of Contents

- [Deployment](#deployment)
- [Authentication Model](#authentication-model)
- [JWT Requirements](#jwt-requirements)
- [Development Testing](#development-testing)
- [Institutional Integration](#institutional-integration)
- [Session Lifecycle](#session-lifecycle)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
---

## Deployment

The recommended way to run M-Autofill is via Docker Compose.

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
docker build -t m-autofill:latest .
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
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_HOURS` | No | `24` | Token lifetime in hours |
| `LLM_MODEL` | No | `openrouter/meta-llama/llama-3.1-8b-instruct` | LLM model identifier |
| `SESSION_TTL_HOURS` | No | `24` | Session expiry in hours |
| `MAX_FILE_SIZE_MB` | No | `50` | Maximum upload file size |
| `AUDIT_RETENTION_DAYS` | No | `365` | Audit log retention period |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

*The service starts without an LLM key but suggestion endpoints will return errors.

---

## Authentication Model

M-Autofill uses a **federated authentication** approach:

- **Production**: Accepts JWT tokens issued by your institutional identity provider (Shibboleth, Azure AD, OIDC-compliant IdP)
- **Development**: Provides `/dev/token` endpoint for easy token generation during testing

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
    secret = "your_jwt_secret"  # Same as M-Autofill's JWT_SECRET

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

## Development Testing

### Using the `/dev/token` Endpoint

For local development and testing, use the built-in token generation endpoint:

**Note**: This endpoint is **automatically disabled** when `ENVIRONMENT=production`.

#### Generate a Token

```bash
curl -X POST http://localhost:8001/dev/token \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "org": "test_org",
    "roles": ["respondent"]
  }'
```

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "test_user",
  "expires_in_hours": 24,
  "message": "Token generated successfully. Use in Authorization header: Bearer <token>"
}
```

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
ENVIRONMENT=development         # or "production"
JWT_SECRET=your_secret_key_here
JWT_EXPIRATION_HOURS=24
```

---

## Institutional Integration

### Integration Workflow

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  User       │         │  Your IdP    │         │  M-Autofill │
│  Browser    │         │  (Shibboleth │         │  API        │
│             │         │   Azure AD)  │         │             │
└──────┬──────┘         └──────┬───────┘         └──────┬──────┘
       │                       │                        │
       │  1. Login Request     │                        │
       ├──────────────────────>│                        │
       │                       │                        │
       │  2. JWT Token         │                        │
       │<──────────────────────┤                        │
       │                       │                        │
       │  3. API Request + JWT │                        │
       ├──────────────────────────────────────────────>│
       │                       │                        │
       │  4. Validate JWT & Process                    │
       │                       │         ┌──────────────┤
       │                       │         │              │
       │                       │         └──────────────>
       │                       │                        │
       │  5. Response          │                        │
       │<──────────────────────────────────────────────┤
       │                       │                        │
```

### Step-by-Step Integration

#### 1. Configure JWT Secret

Both your IdP and M-Autofill must share the same secret:

```bash
# M-Autofill .env
JWT_SECRET=shared_secret_with_idp
JWT_ALGORITHM=HS256
```

#### 2. Map IdP Claims to Required Format

Your IdP must issue tokens with the required claims. Example mapping:

| Your IdP Claim      | M-Autofill Claim | Example                    |
| ------------------- | ---------------- | -------------------------- |
| `sub` or `email`    | `user_id`        | `john.doe@institution.edu` |
| Custom attribute    | `session_id`     | `sess_12345_abc`           |
| `tenant` or `org`   | `org`            | `pxl_university`           |
| `roles` or `groups` | `roles`          | `["respondent"]`           |

#### 3. Test Integration

```bash
# Get token from your IdP (implementation-specific)
IDP_TOKEN=$(curl -X POST https://your-idp.edu/token ...)

# Test with M-Autofill
curl -X GET http://localhost:8001/session/stats \
  -H "Authorization: Bearer $IDP_TOKEN"
```

### Shibboleth Example

If using Shibboleth, configure an attribute release policy to include:

```xml
<AttributeFilterPolicy id="MAutofillPolicy">
    <PolicyRequirementRule xsi:type="Requester" value="https://m-autofill.institution.edu" />
    <AttributeRule attributeID="eduPersonPrincipalName">
        <PermitValueRule xsi:type="ANY" />
    </AttributeRule>
    <AttributeRule attributeID="organizationName">
        <PermitValueRule xsi:type="ANY" />
    </AttributeRule>
</AttributeFilterPolicy>
```

Then map attributes to JWT claims in your token generation service.

### Azure AD / OIDC Example

Configure M-Autofill as a registered application and map claims:

```json
{
  "user_id": "${user.email}",
  "session_id": "${transaction.id}",
  "org": "${company.tenantId}",
  "roles": ["respondent"]
}
```

---

## Session Lifecycle

### Session Creation

Sessions are **automatically created** on first authenticated request:

1. User authenticates with IdP and receives JWT
2. User makes first API request (e.g., `POST /upload`)
3. M-Autofill middleware extracts `session_id` from JWT
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

All endpoints except `/`, `/health`, `/privacy`, and `/dev/token` require authentication.

| Endpoint | Method | Description |
|---|---|---|
| `/upload` | POST | Upload evidence document (PDF, DOCX, TXT, MD) |
| `/suggest` | POST | Single-question answer suggestion with citations and reasoning |
| `/suggest/batch` | POST | Multi-question batch suggestions from QTI-inspired JSON payload |
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
# Development
curl -X POST http://localhost:8001/dev/token

# Production
# Request new token from your IdP
```

### "Invalid token signature"

**Cause**: JWT_SECRET mismatch between IdP and M-Autofill

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

### "Token generation endpoint disabled in production"

**Cause**: Attempting to use `/dev/token` in production environment

**Solution**: Use your institutional IdP for token generation in production

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

## Future Enhancements (Phase 5)

### Planned OAuth 2.0 / OIDC Support

- **OIDC Discovery**: Automatic IdP configuration via `.well-known/openid-configuration`
- **JWKS Validation**: Public key verification instead of shared secrets
- **Token Refresh**: Automatic token renewal without re-authentication
- **Multi-Tenant**: Support for multiple institutional IdPs in single deployment

These features will be added in Phase 5 (May 2026) based on pilot feedback.

---

## Support

- **Technical Issues**: Open issue on GitHub repository
- **Integration Questions**: Contact project maintainers
- **Security Concerns**: Report privately to security@institution.edu

---

**Last Updated**: February 2026  
**Version**: 0.2.0 (Batch Suggest + Reasoning)
