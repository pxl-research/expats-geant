# Change: Add tenant credential routing

## Why

An integrating institution is composed of administratively separated subsidiaries, each
with their own OpenRouter API key and budget. The current system assumes a single
instance per institution with one global API key. Tenant credential routing lets a
single deployment serve multiple subsidiaries, each using their own LLM credentials,
without requiring separate infrastructure per tenant.

## What Changes

- **Tenant registry**: a JSON config file (`tenants.json`) stored outside the
  codebase (mounted volume or `.secrets/` directory). Each tenant has a slug, a hashed
  API secret, an encrypted LLM API key, and an optional LLM base URL. Encrypted at
  rest with Fernet using a server-side master key (`TENANT_ENCRYPTION_KEY`).
- **Default-only mode**: when no tenant registry is present, the system behaves
  exactly as today — single `API_SECRET` and `OPENROUTER_API_KEY` from `.env`. Zero
  configuration change for existing deployments.
- **Auth middleware**: the `/auth/token` endpoint matches the incoming `api_secret`
  against the tenant registry (hashed comparison). On match, the tenant slug is written
  into the JWT `org` claim. OIDC users get their tenant from the Keycloak `groups`
  claim if present, otherwise fall back to the global default.
- **Per-tenant LLM client**: a tenant-keyed cache of `LLMClient` instances, each
  configured with the tenant's decrypted API key and base URL. Created lazily on first
  request for that tenant. The middleware attaches the resolved LLM client to the
  request context.
- **Keycloak group mapping**: a protocol mapper in the realm export adds a `groups`
  claim to the JWT. Admin assigns users to groups matching tenant slugs. No UI changes.

## Impact

- Affected specs: `auth-security`, `llm-integration`
- Affected code:
  - `m_shared/tenant/registry.py` (new — tenant loading, secret verification, key decryption)
  - `m_shared/auth/middleware.py` (tenant resolution from JWT org/groups claim)
  - `cue_api/routes/auth.py`, `shape_api/routes/auth.py` (multi-tenant secret matching)
  - `m_shared/llm/client.py` (no changes — already accepts api_key/base_url in constructor)
  - `run_api.py`, `run_chat_api.py` (tenant-aware LLM client pool instead of single global)
  - `keycloak/realm-export.json` (add groups + group mapper)
  - `.env.example` (document `TENANT_ENCRYPTION_KEY`)
- Not in scope: per-tenant data isolation (sessions are already user-isolated), per-tenant
  rate limiting, tenant management UI/API, tenant-specific model selection
