# Deployment Guide

This guide covers deploying the Expats platform using Docker.

## Services Overview

| Service | Port | Description |
|---|---|---|
| `cue-api` | `8801` | Respondent answer suggestion API |
| `ui` | `8811` | Cue UI survey review frontend (Jinja2 + HTMX) |
| `shape-api` | `8802` | Administrator questionnaire design API |
| `shape_ui` | `8812` | Shape browser UI |
| `keycloak` | `8080` | Bundled identity provider (OIDC) |

All five services start together via `docker-compose up`. Keycloak auto-imports the `expats` realm on first start.

The **Cue Browser Extension** (Chromium + Firefox MV3) is a separate frontend that ships from `cue_extension/` and talks to `cue-api` from the user's browser via CORS. It does not run as a Docker service. See the [Cue Browser Extension](#cue-browser-extension) section below for install, configuration, and the `EXTENSION_ALLOWED_ORIGINS` allow-list.

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
curl http://localhost:8801/health
# Expected: {"status":"healthy"}

# Privacy statement (public endpoint)
curl http://localhost:8801/privacy

# API documentation (disabled when ENVIRONMENT=production)
open http://localhost:8801/docs
```

### 5. Monitor Logs

```bash
# View logs (follow mode)
docker-compose logs -f cue-api

# Check recent logs
docker-compose logs --tail=50 cue-api
```

Container logs are bounded: every service uses the `json-file` driver capped at `max-size: 20m` × `max-file: 5` (~100 MB/service) so logs rotate automatically and cannot fill the disk. Application logs honour `LOG_LEVEL` (default `INFO`); the Shape API additionally logs each chat-turn tool call at `INFO` (e.g. `tool_call ... name=move_question status=ok`) for observability.

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
- **Port**: `8802`
- **Health check**: `http://localhost:8802/health`
- **API docs**: `http://localhost:8802/docs` (disabled when `ENVIRONMENT=production`)
- **Chat UI**: `http://localhost:8812` (service `shape_ui`)

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SESSION_TTL_HOURS` | `24` | Chat session lifetime (hours) |
| `MAX_FILE_SIZE_MB` | `50` | Max upload size for style/content documents |
| `CHAT_PORT` | `8802` | Port for the Shape API |

Shape shares `JWT_SECRET`, `OPENROUTER_API_KEY`, `DEFAULT_LLM_MODEL`, and OIDC variables with Cue. Set them once in `.env`. Each service can use a different LLM via `CUE_LLM_MODEL` and `SHAPE_LLM_MODEL`.

### Verify Shape is running

```bash
curl http://localhost:8802/health
# Expected: {"status":"healthy"}

# API documentation (disabled when ENVIRONMENT=production)
open http://localhost:8802/docs
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
- **Port**: `8811`
- **Health check**: visit `http://localhost:8811` — redirects to Keycloak login

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CUE_API_URL` | `http://cue-api:8801` | Internal (Docker) URL for Cue |
| `CUE_PUBLIC_URL` | `http://localhost:8801` | Browser-accessible URL for Cue. Normally leave unset — derived from `PUBLIC_HOST`. |
| `ALLOW_DEV_TOKEN_LOGIN` | _(unset)_ | Set to `1` or `true` to allow direct JWT login via `?token=` query parameter. **Do not enable in production.** |

### Verify Cue UI is running

```bash
# Open in browser (expects Keycloak login redirect)
open http://localhost:8811
```

---

## Shape UI Service

Shape UI is the browser-based frontend for the questionnaire design co-pilot.

- **Service name**: `shape_ui` (docker-compose)
- **Port**: `8812`

### Additional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SHAPE_API_URL` | `http://shape-api:8802` | Internal (Docker) URL for Shape |
| `SHAPE_PUBLIC_URL` | `http://localhost:8802` | Browser-accessible URL for Shape. Normally leave unset — derived from `PUBLIC_HOST`. |
| `ALLOW_DEV_TOKEN_LOGIN` | _(unset)_ | Set to `1` or `true` to allow direct JWT login via `?token=` query parameter. **Do not enable in production.** |

### Verify Shape UI is running

```bash
open http://localhost:8812
```

---

## Cue Browser Extension

The Cue Browser Extension is a Manifest V3 add-on for Chrome, Edge, and Firefox that fills web forms with evidence-backed answers from a configured Cue API instance. It is the third Cue frontend alongside Cue UI and Shape UI.

- **Source**: `cue_extension/`
- **Talks to**: any reachable `cue-api` deployment (via the URL the user configures in the popup)
- **Runtime**: runs in the user's browser; not a Docker service
- **Targets**: Chrome / Chromium / Edge (Chrome Web Store, Phase F unlisted), Firefox 121+ (AMO, Phase F unlisted)
- **API contract**: see [CUE_API.md → `POST /extract-form`](CUE_API.md#extract-form-fields-llm-fallback)

The extension is user-triggered: nothing leaves the browser without a click on the **Analyse this page** button. It uses the `activeTab` permission (no `<all_urls>` install warning) and requests host permission for the operator-entered Cue origin at runtime.

### Required Configuration: `EXTENSION_ALLOWED_ORIGINS`

The Cue API rejects requests from any browser-extension origin not listed in `EXTENSION_ALLOWED_ORIGINS`. This is the one mandatory deployment knob.

| Variable | Default | Description |
|---|---|---|
| `EXTENSION_ALLOWED_ORIGINS` | _(unset)_ | Comma-separated list of `chrome-extension://<id>` and/or `moz-extension://<id>` origins permitted by CORS. Wildcards (`*`) are rejected at startup; entries with other schemes are dropped with a warning. Leave unset to disable extension access entirely. |

The active allow-list is logged once at cue-api startup (`allowing extension origins: …`).

```bash
# .env at the repo root
EXTENSION_ALLOWED_ORIGINS=chrome-extension://abcdefghijklmnopqrstuvwxyz012345,moz-extension://cue-form-filler@your-org.example
```

Re-create the container after editing:

```bash
docker compose up -d cue-api
```

Chrome assigns a 32-character hex extension ID per-machine for unpacked installs; published listings carry a stable ID. Firefox uses the `gecko.id` from the manifest (default `cue-form-filler@expat-geant.local`).

### Development build & local install

The extension uses a tiny esbuild pipeline. No Docker required.

```bash
cd cue_extension
npm install
npm run build:chrome    # → dist/chrome/
npm run build:firefox   # → dist/firefox/
npm run build:all       # both at once
npm run typecheck       # tsc --noEmit
npm test                # vitest run
```

**Chrome / Edge:**

1. `chrome://extensions` → enable Developer mode → **Load unpacked** → select `cue_extension/dist/chrome/`.
2. Copy the extension ID shown on the card.
3. Add `chrome-extension://<id>` to `EXTENSION_ALLOWED_ORIGINS` in `.env`, then `docker compose up -d cue-api`.
4. Click the toolbar icon, enter your Cue URL (e.g. `http://localhost:8801`), grant the host-permission prompt, log in via API secret.

**Firefox 121+:**

1. `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** → `cue_extension/dist/firefox/manifest.json`.
2. The extension ID is fixed by the manifest's `gecko.id` (see `manifest.json`). Add `moz-extension://<gecko-id>` to `EXTENSION_ALLOWED_ORIGINS`, restart cue-api.
3. Same popup flow as Chrome.

Temporary Firefox add-ons are wiped on browser restart; this path is for development and smoke testing. Signed AMO distribution is the publication path documented below.

### Privacy posture

- The extension sends three things to cue-api: an OIDC/API-secret login, uploaded source documents, and — when the local extractors return nothing — the active page's `innerText` to `POST /extract-form` for LLM-assisted field detection.
- Audit-log entries for extension calls record **URL + item count + model name only**. Form-field values and page text are not persisted to the audit trail. This is enforced server-side (`tests/test_extract_form_api.py::TestAudit`).
- JWTs are stored in `browser.storage.local`. There is no token refresh in v1: on 401 the user logs in again.
- CORS preflights `OPTIONS` requests on protected paths bypass the session middleware so the browser sees a 200 from the CORS layer, not a 401. This is intentional and covered by `tests/test_cors.py::TestPreflightOnProtectedPaths`.

### Production publication (unlisted)

Both stores accept "unlisted" listings, visible only via direct URL — appropriate for pilot deployments and internal-org distribution.

**Chrome Web Store (unlisted):**

1. Register a developer account at <https://chrome.google.com/webstore/devconsole/> (one-time $5 fee).
2. Zip the contents of `dist/chrome/` (not the parent directory). The zip's root must contain `manifest.json` directly.
3. Upload as a new item, choose **Unlisted**, fill the privacy disclosure (justification for `activeTab`, `storage`, and `scripting`).
4. Submit for review. Unlisted reviews are typically faster than public ones because there is no store-search exposure.
5. After publication, the stable extension ID is shown on the listing. Distribute the listing URL to pilot users and add the corresponding `chrome-extension://<id>` to `EXTENSION_ALLOWED_ORIGINS` on the API deployment.

**Mozilla AMO (unlisted, signed `.xpi`):**

1. Register a developer account at <https://addons.mozilla.org/developers/>.
2. From `cue_extension/`, zip the contents of `dist/firefox/` into `cue-form-filler.xpi`.
3. Upload via **Submit a New Add-on** → **On your own**. Mozilla signs the package and emails back the signed `.xpi`.
4. Distribute the signed `.xpi` URL to pilot users. Firefox installs it via direct download; no further allow-listing required at the OS level.
5. The `moz-extension://<gecko-id>` origin matches the manifest's `browser_specific_settings.gecko.id` — this is the value to add to `EXTENSION_ALLOWED_ORIGINS`. No trailing slash: browsers send `Origin: moz-extension://<gecko-id>` and CORS uses exact-match.

### Enterprise force-install (optional)

For organisations distributing the extension as part of a managed deployment:

- **Chrome** — `ExtensionInstallForcelist` policy referencing the Chrome Web Store ID and an update URL.
- **Firefox** — `ExtensionSettings` policy with `installation_mode: force_installed` pointing at the signed `.xpi`.

See the [Chrome Enterprise docs](https://support.google.com/chrome/a/answer/9296680) and [Firefox Policy Templates](https://github.com/mozilla/policy-templates/blob/master/README.md) for the precise JSON shapes; both stores' publication URLs are the only values that need filling in.

### Smoke testing

The full per-browser smoke checklist lives at `scripts/smoke_extension.md` and is the canonical pre-merge validation for extension changes.

---

## Keycloak Service

Keycloak is the bundled identity provider, pre-configured with the `expats` realm.

- **Service name**: `keycloak` (docker-compose)
- **Port**: `8080`
- **Admin console**: `http://localhost:8080` (user: `admin`, password from `KEYCLOAK_ADMIN_PASSWORD`)

The `expats` realm is baked into the Keycloak image (`keycloak/Dockerfile`) and imported on first start; the one-shot `keycloak-init` service then registers the `cue-api` client's redirect URIs on every deploy (see below). OIDC redirect flows are handled by Cue UI (`/auth/callback` on port 8811), which proxies the token back to the browser.

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

When users access the platform from an external machine (not `localhost`), set **one** variable — `PUBLIC_HOST` — to the address browsers use to reach the server (its IP or domain). Everything else is derived from it.

### The only required variable

```bash
PUBLIC_HOST=<HOST>   # e.g. 10.50.70.28  or  surveys.example.org
```

From `PUBLIC_HOST` the stack derives, automatically, for every service:

- the browser-facing base URLs (Cue, Cue UI, Shape, Shape UI),
- the OIDC redirect URIs (`http://<HOST>:8811/auth/callback`, `:8812/auth/callback`),
- Keycloak's public hostname (`KC_HOSTNAME` and `KC_HOSTNAME_ADMIN`).

> ⚠️ **Do not also set** `OIDC_REDIRECT_URI`, `SHAPE_OIDC_REDIRECT_URI`, or the `*_PUBLIC_URL` variables. They are optional overrides that take **precedence** over `PUBLIC_HOST` — a leftover `localhost` value will pin logins to `localhost` even with `PUBLIC_HOST` set correctly. Leave them unset. (The exception is TLS behind a reverse proxy — see [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md#use-https).)
>
> `HOST` stays `0.0.0.0` — that is the internal **bind** address, a different setting from `PUBLIC_HOST`.

### Redirect URIs are registered automatically

The one-shot `keycloak-init` service runs on every deploy, waits for Keycloak, and registers the `cue-api` client's redirect URIs and web origins for both `localhost` and `PUBLIC_HOST`. No manual step is required, and it self-heals after a port or host change. Check its log; it should end with:

```
[keycloak-init] registering redirect URIs for localhost and <HOST>
[keycloak-init] done. cue-api redirect URIs updated; Keycloak applies changes immediately.
```

<details>
<summary>Manual registration (fallback — rarely needed)</summary>

If you ever need to set them by hand, use the admin CLI inside the container (the admin console itself redirects to the Docker-internal `http://keycloak:8080`, so it isn't browser-reachable):

```bash
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin \
  --password <KEYCLOAK_ADMIN_PASSWORD>

docker compose exec keycloak /opt/keycloak/bin/kcadm.sh get clients -r expats \
  --fields id,clientId   # note the cue-api client id

docker compose exec keycloak /opt/keycloak/bin/kcadm.sh update clients/<CLIENT_ID> \
  -r expats \
  -s 'redirectUris=["http://localhost:8811/auth/callback","http://localhost:8812/auth/callback","http://<HOST>:8811/auth/callback","http://<HOST>:8812/auth/callback"]' \
  -s 'webOrigins=["http://localhost:8801","http://localhost:8811","http://localhost:8802","http://localhost:8812","http://<HOST>:8801","http://<HOST>:8811","http://<HOST>:8802","http://<HOST>:8812"]' \
  -s 'attributes."post.logout.redirect.uris"="http://localhost:8811##http://localhost:8812##http://<HOST>:8811##http://<HOST>:8812"'
```

No restart needed — Keycloak applies client config changes immediately.

</details>

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
  -p 8801:8801 \
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

# API available at http://localhost:8801
# Docs at http://localhost:8801/docs (disabled when ENVIRONMENT=production)
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
| `PORT`                   | `8801`                       | API server port                                                |
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
curl -X POST http://localhost:8801/auth/token \
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
TOKEN=$(curl -s -X POST http://localhost:8801/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test_user","api_secret":"your-shared-api-secret"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Step 2: Upload a document
curl -X POST http://localhost:8801/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_document.pdf"

# Step 3: Get answer suggestion
curl -X POST http://localhost:8801/suggest/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assessment_id": "quick-check",
    "items": [{"id": "q1", "type": "open_ended", "prompt": "What is my employment status?", "choices": []}]
  }'

# Step 4: Check session stats
curl -X GET http://localhost:8801/session/stats \
  -H "Authorization: Bearer $TOKEN"

# Step 5: Get audit report
curl -X GET http://localhost:8801/audit-report \
  -H "Authorization: Bearer $TOKEN"

# Step 6: Delete session (cleanup)
curl -X DELETE http://localhost:8801/session \
  -H "Authorization: Bearer $TOKEN"
```

#### 4. Python Testing Example

```python
import requests

# Generate token
response = requests.post(
    "http://localhost:8801/auth/token",
    json={"user_id": "python_tester", "api_secret": "your-shared-api-secret"}
)
token = response.json()["token"]

# Use token for authenticated requests
headers = {"Authorization": f"Bearer {token}"}

# Upload document
with open("document.pdf", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8801/upload",
        headers=headers,
        files={"file": f}
    )
print(upload_response.json())

# Get suggestion
suggest_response = requests.post(
    "http://localhost:8801/suggest/batch",
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
curl http://localhost:8801/health
# Expected: {"status":"healthy"}

# API root
curl http://localhost:8801/
# Expected: {"service":"cue-api","status":"running"}
```

### Public Endpoints (No Auth Required)

```bash
# Privacy statement
curl http://localhost:8801/privacy

# API documentation (interactive; disabled when ENVIRONMENT=production)
open http://localhost:8801/docs
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
        proxy_pass http://localhost:8801;
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
curl -X POST http://localhost:8801/admin/reload-tenants \
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
