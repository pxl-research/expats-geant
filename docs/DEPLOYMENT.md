# Deployment Guide

This guide covers deploying the Expats platform using Docker.

## Services Overview

| Service | Port | Description |
|---|---|---|
| `cue-api` | `8001` | Respondent answer suggestion API |
| `ui` | `8002` | Cue UI survey review frontend (Jinja2 + HTMX) |
| `shape-api` | `8003` | Administrator questionnaire design API |
| `shape_ui` | `8004` | Shape browser UI |
| `keycloak` | `8080` | Bundled identity provider (OIDC) |

All five services start together via `docker-compose up`. Keycloak auto-imports the `expats` realm on first start.

## Prerequisites

- Docker & Docker Compose installed
- OpenRouter or OpenAI API key
- Basic understanding of environment variables

## Quick Start (Docker Compose)

This is the **recommended** deployment method.

### 1. Clone and Configure

```bash
git clone https://github.com/pxl-research/expats-geant.git
cd expats-geant

# Copy environment template
cp .env.example .env
```

### 2. Edit Configuration

Open `.env` and set **required** values:

```bash
# Required: Add your API key (choose one or both)
OPENROUTER_API_KEY=sk-or-v1-xxxxx  # Get from https://openrouter.ai/keys
# OR
OPENAI_API_KEY=sk-xxxxx            # Get from https://platform.openai.com

# Required: Change JWT secret (use a secure random string)
JWT_SECRET=your-secure-random-secret-here-min-32-chars

# Optional: LLM models (per-service overrides, falls back to DEFAULT_LLM_MODEL)
DEFAULT_LLM_MODEL=anthropic/claude-haiku-4.5
CUE_LLM_MODEL=anthropic/claude-sonnet-4.6
SHAPE_LLM_MODEL=google/gemini-3-flash-preview
```

**💡 Tip:** Generate a secure JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start the Service

```bash
# Build and start
docker-compose up --build

# Or run in background (detached mode)
docker-compose up -d --build
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:8001/health
# Expected: {"status":"healthy"}

# Privacy statement (public endpoint)
curl http://localhost:8001/privacy

# API documentation (disabled when ENVIRONMENT=production)
open http://localhost:8001/docs
```

### 5. Monitor Logs

```bash
# View logs (follow mode)
docker-compose logs -f cue-api

# Check recent logs
docker-compose logs --tail=50 cue-api
```

### 6. Stop the Service

```bash
# Stop containers (data persists)
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

## Shape Service

Shape is the questionnaire design co-pilot API.

- **Service name**: `shape-api` (docker-compose)
- **Port**: `8003`
- **Health check**: `http://localhost:8003/health`
- **API docs**: `http://localhost:8003/docs` (disabled when `ENVIRONMENT=production`)
- **Chat UI**: `http://localhost:8004` (service `shape_ui`)

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SESSION_TTL_HOURS` | `24` | Chat session lifetime (hours) |
| `MAX_FILE_SIZE_MB` | `50` | Max upload size for style/content documents |
| `CHAT_PORT` | `8003` | Port for the Shape API |

Shape shares `JWT_SECRET`, `OPENROUTER_API_KEY`, `DEFAULT_LLM_MODEL`, and OIDC variables with Cue. Set them once in `.env`. Each service can use a different LLM via `CUE_LLM_MODEL` and `SHAPE_LLM_MODEL`.

### Verify Shape is running

```bash
curl http://localhost:8003/health
# Expected: {"status":"healthy"}

# API documentation (disabled when ENVIRONMENT=production)
open http://localhost:8003/docs
```

### Monitor Shape logs

```bash
docker-compose logs -f shape-api
```

See [SHAPE_API.md](SHAPE_API.md) for the full API reference.

---

## Cue UI Service

Cue UI is the browser-based survey review frontend for respondents.

- **Service name**: `ui` (docker-compose)
- **Port**: `8002`
- **Health check**: visit `http://localhost:8002` — redirects to Keycloak login

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CUE_API_URL` | `http://cue-api:8001` | Internal (Docker) URL for Cue |
| `CUE_PUBLIC_URL` | `http://localhost:8001` | Browser-accessible URL for Cue |
| `ALLOW_DEV_TOKEN_LOGIN` | _(unset)_ | Set to `1` or `true` to allow direct JWT login via `?token=` query parameter. **Do not enable in production.** |

### Verify Cue UI is running

```bash
# Open in browser (expects Keycloak login redirect)
open http://localhost:8002
```

---

## Shape UI Service

Shape UI is the browser-based frontend for the questionnaire design co-pilot.

- **Service name**: `shape_ui` (docker-compose)
- **Port**: `8004`

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SHAPE_API_URL` | `http://shape-api:8003` | Internal (Docker) URL for Shape |
| `SHAPE_PUBLIC_URL` | `http://localhost:8003` | Browser-accessible URL for Shape |
| `ALLOW_DEV_TOKEN_LOGIN` | _(unset)_ | Set to `1` or `true` to allow direct JWT login via `?token=` query parameter. **Do not enable in production.** |

### Verify Shape UI is running

```bash
open http://localhost:8004
```

---

## Keycloak Service

Keycloak is the bundled identity provider, pre-configured with the `expats` realm.

- **Service name**: `keycloak` (docker-compose)
- **Port**: `8080`
- **Admin console**: `http://localhost:8080` (user: `admin`, password from `KEYCLOAK_ADMIN_PASSWORD`)

The realm import in `keycloak/` is loaded automatically on first start. OIDC redirect flows are handled by Cue UI (`/auth/callback` on port 8002), which proxies the token back to the browser.

**Local dev note**: The Keycloak *master* realm defaults to `sslRequired: external`, which blocks the admin console over plain HTTP in Docker. The imported *expats* realm is unaffected. To access the admin console locally, run this one-time command (resets when the container is recreated):

```bash
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin \
  --password <KEYCLOAK_ADMIN_PASSWORD>
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh update realms/master \
  -s sslRequired=NONE
```

For production deployments behind a TLS-terminating reverse proxy, keep `sslRequired` set to `external` (the default) for both realms.

```bash
docker-compose logs -f keycloak
```

---

## Non-Localhost Deployment

When users access the platform from an external machine (not `localhost`), several additional environment variables must be set. Replace `<HOST>` with your server's IP or domain.

### Required additional variables

```bash
# Browser-accessible URLs for each service
CUE_PUBLIC_URL=http://<HOST>:8001
OIDC_REDIRECT_URI=http://<HOST>:8002/auth/callback
CUE_UI_PUBLIC_URL=http://<HOST>:8002
SHAPE_PUBLIC_URL=http://<HOST>:8003
SHAPE_OIDC_REDIRECT_URI=http://<HOST>:8004/auth/callback
SHAPE_UI_PUBLIC_URL=http://<HOST>:8004

# Public URL of Keycloak as seen by the browser
# Without this, the OIDC login redirect sends users to http://keycloak:8080/... (Docker-internal, unreachable)
KEYCLOAK_PUBLIC_URL=http://<HOST>:8080

# Makes the Keycloak admin console redirect to your host instead of http://keycloak:8080/admin/
KC_HOSTNAME_ADMIN=http://<HOST>:8080
```

### Register deployed redirect URIs in Keycloak

The `realm-export.json` only contains localhost redirect URIs. After first startup you must add your deployed URIs. The Keycloak admin console itself redirects to `http://keycloak:8080` in the browser (Docker-internal), so use the admin CLI inside the container:

```bash
# Authenticate
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password <KEYCLOAK_ADMIN_PASSWORD>

# Find the cue-api client ID
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh get clients -r expats \
  --fields id,clientId

# Update redirect URIs and web origins (replace <CLIENT_ID> and <HOST>)
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh update clients/<CLIENT_ID> \
  -r expats \
  -s 'redirectUris=["http://localhost:8002/auth/callback","http://localhost:8004/auth/callback","http://<HOST>:8002/auth/callback","http://<HOST>:8004/auth/callback"]' \
  -s 'webOrigins=["http://localhost:8001","http://localhost:8002","http://localhost:8003","http://localhost:8004","http://<HOST>:8001","http://<HOST>:8002","http://<HOST>:8003","http://<HOST>:8004"]' \
  -s 'attributes."post.logout.redirect.uris"="http://localhost:8002##http://localhost:8004##http://<HOST>:8002##http://<HOST>:8004"'
```

No restart needed — Keycloak applies client config changes immediately.

### Rebuild API services after changing oauth config

If you updated `m_shared/auth/oauth.py` (e.g. after a `git pull`), rebuild the API services:

```bash
docker compose up -d --build cue-api shape-api
```

---

## Manual Docker Deployment

If you prefer not to use Docker Compose:

### Build the Image

```bash
docker build -t cue-api:latest .
```

### Run the Container

```bash
docker run -d \
  --name cue-api \
  -p 8001:8001 \
  -e JWT_SECRET="your-secure-secret-here" \
  -e OPENROUTER_API_KEY="sk-or-v1-xxxxx" \
  -e SESSION_TTL_HOURS=24 \
  -e MAX_FILE_SIZE_MB=50 \
  -v sessions_data:/app/data/sessions \
  -v chroma_data:/app/data/chroma \
  --restart unless-stopped \
  cue-api:latest
```

### Container Management

```bash
# View logs
docker logs -f cue-api

# Stop container
docker stop cue-api

# Start stopped container
docker start cue-api

# Remove container
docker rm -f cue-api
```

## Local Development (Without Docker)

For development without Docker:

### Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
# Start API server
python3 run_api.py

# API available at http://localhost:8001
# Docs at http://localhost:8001/docs (disabled when ENVIRONMENT=production)
```

## Environment Variables Reference

### Required

| Variable             | Description                  | Example                |
| -------------------- | ---------------------------- | ---------------------- |
| `OPENROUTER_API_KEY` | OpenRouter API key           | `sk-or-v1-xxxxx`       |
| `OPENAI_API_KEY`     | OpenAI API key (alternative) | `sk-xxxxx`             |
| `JWT_SECRET`         | Secret for JWT signing       | 32+ char random string |

### Optional

| Variable                 | Default                      | Description                                                    |
| ------------------------ | ---------------------------- | -------------------------------------------------------------- |
| `DEFAULT_LLM_MODEL`      | `anthropic/claude-haiku-4.5` | Shared fallback LLM model                                      |
| `CUE_LLM_MODEL`          | `anthropic/claude-sonnet-4.6` | LLM model for Cue (answer suggestions)                        |
| `SHAPE_LLM_MODEL`        | `google/gemini-3-flash-preview` | LLM model for Shape (survey authoring)                      |
| `API_SECRET`             | —                            | Shared secret for `POST /auth/token` (omit to disable)         |
| `SESSION_TTL_HOURS`      | `24`                         | Session lifetime (hours)                                       |
| `MAX_FILE_SIZE_MB`       | `50`                         | Upload limit (MB)                                              |
| `AUDIT_RETENTION_DAYS`   | `365`                        | Audit log retention (days)                                     |
| `CUE_QUERY_REWRITE`      | `true`                       | Enable LLM query rewriting before vector search                |
| `CUE_REWRITE_BATCH_SIZE` | `20`                         | Max questions per rewrite LLM call                             |
| `CUE_REWRITE_MODEL`      | —                            | Dedicated model for rewriting (e.g. `google/gemini-2.5-flash`) |
| `CUE_WEB_INGEST_ENABLED` | `false`                      | Enable web URL ingestion (server-side fetches; per-session opt-in still required) |
| `THINKING_BUDGET_TOKENS` | —                            | Token budget for extended thinking (Claude 3.5+/4.x only)      |
| `PORT`                   | `8001`                       | API server port                                                |
| `LOG_LEVEL`              | `INFO`                       | Logging level                                                  |

## Testing Your Deployment

### Quick Testing with the API Token Endpoint

`POST /auth/token` issues a JWT to any caller presenting the correct `API_SECRET`. It
works in **all environments** — no separate dev endpoint needed.

#### 1. Set `API_SECRET` in `.env`

```bash
API_SECRET=your-shared-api-secret   # add this to .env
```

#### 2. Generate a Token

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

#### 3. Complete Workflow Example

```bash
# Step 1: Generate token
TOKEN=$(curl -s -X POST http://localhost:8001/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_user","api_secret":"your-shared-api-secret"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Step 2: Upload a document
curl -X POST http://localhost:8001/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_document.pdf"

# Step 3: Get answer suggestion
curl -X POST http://localhost:8001/suggest/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assessment_id": "quick-check",
    "items": [{"id": "q1", "type": "open_ended", "prompt": "What is my employment status?", "choices": []}]
  }'

# Step 4: Check session stats
curl -X GET http://localhost:8001/session/stats \
  -H "Authorization: Bearer $TOKEN"

# Step 5: Get audit report
curl -X GET http://localhost:8001/audit-report \
  -H "Authorization: Bearer $TOKEN"

# Step 6: Delete session (cleanup)
curl -X DELETE http://localhost:8001/session \
  -H "Authorization: Bearer $TOKEN"
```

#### 4. Python Testing Example

```python
import requests

# Generate token
response = requests.post(
    "http://localhost:8001/auth/token",
    json={"user_id": "python_tester", "api_secret": "your-shared-api-secret"}
)
token = response.json()["token"]

# Use token for authenticated requests
headers = {"Authorization": f"Bearer {token}"}

# Upload document
with open("document.pdf", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8001/upload",
        headers=headers,
        files={"file": f}
    )
print(upload_response.json())

# Get suggestion
suggest_response = requests.post(
    "http://localhost:8001/suggest/batch",
    headers=headers,
    json={
        "assessment_id": "quick-check",
        "items": [{"id": "q1", "type": "open_ended", "prompt": "What is my current role?", "choices": []}],
    }
)
print(suggest_response.json())
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8001/health
# Expected: {"status":"healthy"}

# API root
curl http://localhost:8001/
# Expected: {"service":"cue-api","status":"running"}
```

### Public Endpoints (No Auth Required)

```bash
# Privacy statement
curl http://localhost:8001/privacy

# API documentation (interactive; disabled when ENVIRONMENT=production)
open http://localhost:8001/docs
```

### Manual JWT Token Generation (Advanced)

If you need to generate tokens manually (e.g., for institutional integration testing):

```python
# manual_token.py
import jwt
from datetime import datetime, timedelta, timezone

secret = "your-jwt-secret-from-env"
payload = {
    "user_id": "institutional_user",
    "session_id": "sess_12345",
    "org": "institution_name",
    "roles": ["respondent"],
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
```

### Running Integration Tests

Run the full test suite to verify deployment:

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v

# Specific test suites
python3 -m pytest tests/test_session_api.py -v    # API tests
python3 -m pytest tests/test_auth_token.py -v     # API token endpoint tests
python3 -m pytest tests/test_auth.py -v           # Auth tests
```

### Institutional Integration

For production deployments with institutional authentication, see:

📖 **[docs/CUE_API.md](CUE_API.md)** — Complete integration guide with:

- JWT requirements and claim structure
- Shibboleth / Azure AD / OIDC examples
- Troubleshooting common auth issues
- Security best practices

## Troubleshooting

### Container won't start

**Check logs:**

```bash
docker logs cue-api
```

**Common issues:**

- Missing API key → Check `.env` file has `OPENROUTER_API_KEY` or `OPENAI_API_KEY`
- Port conflict → Change port in docker-compose.yml or stop conflicting service
- Invalid JWT secret → Ensure `JWT_SECRET` is set and at least 32 characters

### "No LLM API key found" warning

The service will start but suggestion endpoints won't work without an API key.

**Fix:** Add to `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Then restart:

```bash
docker-compose restart
```

### Permission denied on volumes

**Linux users may need:**

```bash
sudo chown -R $(whoami):$(whoami) .
```

### Can't connect to Docker daemon

**macOS:** Start Docker Desktop application

**Linux:**

```bash
sudo systemctl start docker
```

## Data Persistence

Docker volumes persist data across container restarts:

- `sessions_data` - User-scoped session files (`{user_hash}/{session_id}/`) and audit logs
- `chroma_data` - Vector database (document embeddings)

**Backup volumes:**

```bash
docker run --rm \
  -v sessions_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/sessions-backup.tar.gz /data
```

**Restore volumes:**

```bash
docker run --rm \
  -v sessions_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/sessions-backup.tar.gz -C /
```

## Security Considerations

### Production Deployment

Set `ENVIRONMENT=production` in your `.env` file. This enables several hardening features:

1. **Startup secret guard** — services refuse to start if `JWT_SECRET` or `OIDC_CLIENT_SECRET` are still set to placeholder values (e.g. `change-me`, `change-me-in-production`)
2. **API docs disabled** — `/docs`, `/redoc`, and `/openapi.json` are disabled (they expose the full API schema)
3. **Non-root containers** — all Docker containers run as a non-root `appuser`
4. **Security headers** — all UI responses include CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Cache-Control: no-store, and Permissions-Policy headers
5. **Security logging** — both Cue API and Shape API write auth events to `logs/security.log` (rotating, 5MB, 3 backups)

Additional production steps:

6. **Change all secrets** — `JWT_SECRET` (32+ chars), `OIDC_CLIENT_SECRET` (regenerate in Keycloak), `KEYCLOAK_ADMIN_PASSWORD`
7. **Enable HTTPS** — use a reverse proxy (nginx, Caddy, Traefik) for TLS termination
8. **Enable HSTS** — set `ENABLE_HSTS=true` in `.env` when behind a TLS-terminating proxy
9. **Configure Keycloak** — set password policy and enable MFA (see [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md))
10. **Firewall rules** — restrict access to API ports
11. **Monitor logs** — set up log aggregation and alerting
12. **Backup data** — regular backups of Docker volumes
13. **Network isolation** — use Docker networks for multi-service deployments

### Example Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Multi-Tenant Setup

By default, the platform operates in **single-tenant mode** — all users share the global `OPENROUTER_API_KEY`. When an institution has subsidiaries (e.g. faculties) that each manage their own LLM budget, multi-tenant mode routes LLM calls through per-tenant API keys.

### When to use

- Multiple subsidiaries share one deployment
- Each subsidiary has its own OpenRouter (or other LLM provider) API key
- You want LLM cost attribution per subsidiary

### Setup

**1. Generate an encryption key:**

```bash
python scripts/manage_tenants.py generate-key
```

Set the output as `TENANT_ENCRYPTION_KEY` in your `.env`.

**2. Create tenant credentials:**

```bash
python scripts/manage_tenants.py create \
    --slug faculty-a \
    --name "Faculty of Sciences" \
    --api-key sk-or-v1-your-openrouter-key
```

The script outputs a JSON block and a one-time API secret. Give the secret to the tenant; add the JSON block to `.secrets/tenants.json`:

```json
{
  "tenants": {
    "faculty-a": {
      "name": "Faculty of Sciences",
      "api_secret_hash": "sha256:...",
      "api_key_encrypted": "gAAAAA...",
      "base_url": "https://openrouter.ai/api/v1"
    }
  }
}
```

**3. Configure environment:**

```bash
TENANT_REGISTRY_PATH=.secrets/tenants.json
TENANT_ENCRYPTION_KEY=<your-generated-key>
```

**4. Restart services.** Tenants are loaded at startup. You can also hot-reload without restart:

```bash
curl -X POST http://localhost:8001/admin/reload-tenants \
  -H "Authorization: Bearer <API_SECRET>"
```

### How it works

- **API users**: POST `/auth/token` with a tenant's API secret → JWT contains `org=<tenant-slug>` → LLM calls use that tenant's API key.
- **OIDC users**: Assign users to Keycloak groups matching tenant slugs (e.g. group `faculty-a`). The groups claim in the ID token resolves the tenant automatically.
- **No tenant match**: Falls back to the global `OPENROUTER_API_KEY` (single-tenant behaviour).

### Keycloak group assignment

The realm export includes example groups (`faculty-a`, `faculty-b`) and a `group-membership` protocol mapper that injects groups into the JWT. To assign a user to a tenant:

1. Open the Keycloak admin console → Users → select user → Groups tab
2. Add the user to the group matching their tenant slug

### Backwards compatibility

When `TENANT_REGISTRY_PATH` is not set (or the file doesn't exist), the system behaves identically to a single-tenant deployment. No configuration changes are needed for existing deployments.

---

## Support

- Documentation: [README.md](../README.md)
- Integration guide: [docs/CUE_API.md](CUE_API.md)
- Project specs: [openspec/project.md](../openspec/project.md)
- Issues: [GitHub Issues](https://github.com/pxl-research/expats-geant/issues)
