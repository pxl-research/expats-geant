# Operator Runbook

This guide is for IT administrators and data protection officers at institutions deploying
the Expats platform (Shape + Cue). It covers decisions to make before deployment, initial
setup, GDPR compliance steps, and ongoing operations.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the technical Docker setup reference.

---

## 1. Before You Deploy — Decision Checklist

Work through these decisions before running `docker-compose up`.

### 1.1 LLM Provider

Both Shape (questionnaire design) and Cue (answer suggestions) require an LLM.
Choose the option that fits your institution's data governance requirements:

| Option | Data locality | Setup effort | Recommended for |
|--------|--------------|--------------|-----------------|
| **Self-hosted** (Ollama, LM Studio) | Full on-premise — no data leaves your servers | Medium — requires GPU or capable server | Institutions with strict data sovereignty requirements |
| **OpenRouter EU endpoint** (`eu.openrouter.ai`) | EU in-region — data stays within the EU | Low — standard API key, enterprise account required | Most EU R&E institutions; good default choice |
| **OpenRouter standard** (`openrouter.ai`) | Routing not guaranteed EU | Low | Acceptable with a data processing addendum (DPA) in place |
| **Direct OpenAI / Anthropic** | Non-EU data centres | Low | Requires Standard Contractual Clauses (SCCs) under GDPR Art. 46 |

**Recommendation for EU institutions:** Use OpenRouter's EU endpoint or a self-hosted model.
For OpenRouter EU routing, set in your `.env`:
```bash
LLM_BASE_URL=https://eu.openrouter.ai/api/v1
OPENROUTER_API_KEY=sk-or-v1-your-key
```
Note: EU in-region routing requires an enterprise OpenRouter account. Contact OpenRouter to enable it.

For self-hosted (Ollama example):
```bash
LLM_BASE_URL=http://your-ollama-host:11434/v1
OPENROUTER_API_KEY=ollama   # placeholder, not validated
DEFAULT_LLM_MODEL=llama3.2  # or whichever model you've pulled
```

### 1.2 Authentication

Expats bundles Keycloak as the identity provider. Decide how users will authenticate:

- [ ] **Keycloak local accounts** — users register directly in Keycloak. No integration required. Suitable for pilots and small deployments.
- [ ] **Institutional SSO (SAML/Shibboleth)** — federate Keycloak with your existing IdP. No application code changes; configured in the Keycloak admin panel. See [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md).
- [ ] **Azure AD / Microsoft 365** — connect via Keycloak's Microsoft identity provider. See [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md).
- [ ] **LDAP / Active Directory** — user federation via Keycloak. See [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md).

### 1.3 Data Retention

Configure these values in `.env` before first launch:

| Variable | Default | Guidance |
|----------|---------|----------|
| `SESSION_TTL_HOURS` | `24` | How long a Cue session (uploaded documents + vectors) persists. 24–48h is typical for a single form-filling session. |
| `AUDIT_RETENTION_DAYS` | `365` | How long audit reports are kept after a session ends. Align with your institution's records retention policy. 365 days (1 year) is the recommended default. |

Operational data (uploaded documents, vector indices) is deleted automatically when a session
expires. Audit reports are retained for the configured period and then permanently deleted.

### 1.4 Network Exposure

- [ ] Is the platform accessible only on your internal network (intranet)?
- [ ] Will it be exposed to the internet?
- [ ] Verify `ALLOW_DEV_TOKEN_LOGIN` is **not** set in production (it allows bypassing OIDC login via `?token=` query parameter)

If internet-facing: set up TLS termination (nginx, Caddy, Traefik) and update OIDC redirect URIs.
See [DEPLOYMENT.md — Security Considerations](DEPLOYMENT.md#security-considerations).

---

## 2. GDPR / DPO Checklist

Complete this before going live with real users.

- [ ] **Lawful basis documented** — consent is captured at session start via the `/privacy` endpoint; ensure your DPO has reviewed the consent statement
- [ ] **DPIA conducted** — a Data Protection Impact Assessment is recommended given AI processing of potentially sensitive form responses
- [ ] **Data processing addendum** — if using an external LLM API (OpenRouter, OpenAI), ensure a DPA is in place with the provider
- [ ] **No special-category data** — instruct users not to upload documents containing health, religious, political, or biometric data unless explicitly consented and configured
- [ ] **Retention periods set** — `AUDIT_RETENTION_DAYS` aligned with institutional policy (section 1.3)
- [ ] **Right to erasure** — users can delete their session and all associated data via the UI (`DELETE /session`) or by session expiry
- [ ] **Data controller identity** — your institution is the data controller; document this in your internal records
- [ ] **DPO contact available** — ensure users can reach your DPO if they have questions about their data

---

## 3. Initial Deployment

### Step 1 — Clone and configure

```bash
git clone https://github.com/pxl-research/expats-geant.git
cd expats-geant
cp .env.example .env
```

### Step 2 — Edit `.env`

Required values:
```bash
# LLM provider (see section 1.1)
OPENROUTER_API_KEY=sk-or-v1-your-key
LLM_BASE_URL=https://eu.openrouter.ai/api/v1   # EU endpoint
DEFAULT_LLM_MODEL=anthropic/claude-haiku-4.5     # shared fallback
CUE_LLM_MODEL=anthropic/claude-sonnet-4.6       # Cue answer suggestions
SHAPE_LLM_MODEL=google/gemini-3-flash-preview   # Shape survey authoring

# Security — generate a strong secret
JWT_SECRET=<run: python3 -c "import secrets; print(secrets.token_urlsafe(32))">

# Keycloak admin — change before going live
KEYCLOAK_ADMIN_PASSWORD=<strong-random-password>

# Retention (align with your policy)
SESSION_TTL_HOURS=24
AUDIT_RETENTION_DAYS=365
```

### Step 3 — Set production environment

```bash
# In .env — enables startup secret guard and disables API docs
ENVIRONMENT=production

# Enable HSTS if behind a TLS-terminating reverse proxy
ENABLE_HSTS=true
```

### Step 4 — Change Keycloak client secret

The default client secret in `keycloak/realm-export.json` is `change-me`.
Update it before production:
1. Start Keycloak: `docker-compose up keycloak`
2. Go to `http://localhost:8080/admin` → Clients → `cue-api` → Credentials → Regenerate
3. Set `OIDC_CLIENT_SECRET=<new-secret>` in `.env`

### Step 5 — Configure Keycloak security

The bundled realm includes a password policy (min 12 chars) and opt-in TOTP. Review and adjust:

- **Password policy**: Keycloak admin → Realm Settings → Authentication → Password Policy
- **MFA**: To make TOTP mandatory, set "Configure OTP" as a Default Action under Authentication → Required Actions
- See [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md) for details

### Step 6 — Start all services

```bash
docker-compose up -d --build
```

### Step 7 — Verify

```bash
curl http://localhost:8001/health   # Cue API
curl http://localhost:8003/health   # Shape API
open http://localhost:8002          # Cue UI (redirects to Keycloak login)
open http://localhost:8004          # Shape UI
open http://localhost:8080/admin    # Keycloak admin console
```

---

## 4. Onboarding Users

### For administrators using Shape (questionnaire design)

1. Create a Keycloak account for each administrator (or configure SSO federation)
2. Share the Shape UI URL: `http(s)://your-host:8004`
3. Provide the [STYLE_GUIDE_TEMPLATE.md](STYLE_GUIDE_TEMPLATE.md) — ask them to fill it in and upload it in the Style setup step when starting a new session
4. Recommend they start with a small existing questionnaire to get familiar with the suggestion, validation, and tagging features

### For respondents using Cue (answer suggestions)

1. Create Keycloak accounts or enable self-registration in the Keycloak admin console
2. Share the Cue UI URL: `http(s)://your-host:8002`
3. Brief users: they upload their personal documents (CVs, reports, etc.) at the start of a session, then use the AI suggestions when filling out the form
4. Remind users: uploaded documents are automatically deleted after the session expires; they can also delete immediately via the UI

---

## 5. Monitoring and Maintenance

### Health checks

All services expose `/health` endpoints. For automated monitoring:
```bash
curl -f http://localhost:8001/health || alert "Cue API down"
curl -f http://localhost:8003/health || alert "Shape API down"
```

### Logs

```bash
docker-compose logs -f cue-api     # Cue API logs
docker-compose logs -f shape-api   # Shape API logs
docker-compose logs -f keycloak    # Authentication logs
```

Security events are written to `logs/security.log` inside the container (mapped to host if volume-mounted).

### Backups

Back up Docker volumes regularly — they contain session data and audit logs:
```bash
docker run --rm \
  -v sessions_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/sessions-$(date +%Y%m%d).tar.gz /data
```

### Updates

```bash
git pull
docker-compose up -d --build
```

Test health endpoints after updating. No database migrations are required — all storage is file-based.

---

## 6. Configuring Shape's Institutional Style

Shape can be configured with your institution's questionnaire writing style. This applies to all sessions by default when a style guide document is uploaded.

**Option A — Upload during session setup (per-session)**
1. Fill in [STYLE_GUIDE_TEMPLATE.md](STYLE_GUIDE_TEMPLATE.md) for your institution
2. When starting a Shape session, go to Style Setup and upload the filled template
3. Shape extracts and summarises the rules automatically

**Option B — API-level default (for institutional admins)**
Use the Style Update endpoint to set a persistent style profile for a session:
```bash
curl -X POST http://localhost:8003/chat/{session_id}/style \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "en",
    "free_text": "Use plain professional language. Prefer 5-point Likert scales. Avoid binary yes/no options. Use gender-neutral phrasing. Keep questions under 20 words."
  }'
```

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Service exits immediately in production | Placeholder secrets detected (`JWT_SECRET` or `OIDC_CLIENT_SECRET` still set to defaults) | Set real secrets in `.env` — the startup guard blocks placeholder values when `ENVIRONMENT=production` |
| Cue/Shape API won't start | Missing `OPENROUTER_API_KEY` or `JWT_SECRET` | Check `.env` and restart |
| Keycloak login fails | Wrong `OIDC_CLIENT_SECRET` | Regenerate in Keycloak admin → update `.env` |
| LLM suggestions not working | Invalid or missing API key | Check `docker-compose logs cue-api` for LLM errors |
| Sessions not persisting | Volume not mounted | Check `volumes:` section in `docker-compose.yml` |
| "Permission denied" on volumes (Linux) | File ownership | `sudo chown -R $(whoami):$(whoami) .` |
| EU data locality concern | Standard OpenRouter endpoint in use | Switch `LLM_BASE_URL` to `https://eu.openrouter.ai/api/v1` |

For more troubleshooting, see [DEPLOYMENT.md — Troubleshooting](DEPLOYMENT.md#troubleshooting).

---

## 8. Contact and Support

- Technical issues: [GitHub Issues](https://github.com/pxl-research/expats-geant/issues)
- API reference (Cue): [CUE_API.md](CUE_API.md)
- API reference (Shape): [SHAPE_API.md](SHAPE_API.md)
- Deployment reference: [DEPLOYMENT.md](DEPLOYMENT.md)
- Keycloak / SSO setup: [KEYCLOAK_SETUP.md](KEYCLOAK_SETUP.md)
- Project lead: servaas.tilkin@pxl.be
