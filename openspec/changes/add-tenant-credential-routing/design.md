## Context

The platform currently assumes one deployment per institution with a single OpenRouter
API key. A partner institution has subsidiaries that each manage their own LLM budget.
They want to share one Expats deployment but route LLM calls through their own API keys.

The JWT already carries an `org` claim (currently hardcoded to `"api"` or `"default"`).
The LLM client constructor already accepts `api_key` and `base_url` parameters. The
main work is connecting these two: resolve tenant from auth, look up credentials, pass
them to the right LLM client instance.

## Goals / Non-Goals

**Goals:**
- Multiple tenants share one deployment, each with their own LLM credentials
- System works identically with no tenant config (backwards compatible)
- Tenant API secrets stored hashed; LLM API keys encrypted at rest
- OIDC users can be associated with a tenant via Keycloak groups
- Tenant resolution is transparent to route handlers

**Non-Goals:**
- Per-tenant data isolation beyond existing session isolation
- Tenant management CRUD API or admin UI
- Per-tenant model selection or rate limiting
- Tenant billing or usage tracking
- Dynamic tenant creation at runtime (config file is static, loaded at startup)

## Decisions

### Tenant registry as a JSON file

**Decision:** Tenants are defined in a single JSON config file loaded at startup.

**Alternatives considered:**
- *Database table*: More flexible, supports dynamic CRUD, but adds a database
  dependency the project doesn't have yet (PostgreSQL is listed as "future").
- *Environment variables*: One `TENANT_X_API_KEY` per tenant. Simple but doesn't
  scale and can't store structured data cleanly.

**Rationale:** A JSON file is readable, diffable, and requires no infrastructure.
The expected tenant count is small (2-10 subsidiaries). The file lives outside the
repo (mounted volume or `.secrets/` directory) for security. Restart required to
pick up changes — acceptable for PoC.

### Fernet encryption for stored API keys

**Decision:** Tenant LLM API keys are encrypted with Fernet symmetric encryption
using a server-side `TENANT_ENCRYPTION_KEY` env var. Tenant API secrets (the ones
tenants send to authenticate) are stored as SHA-256 hashes.

**Rationale:** The `cryptography` package is already installed as a transitive
dependency of PyJWT and Authlib. Fernet provides authenticated encryption in ~5
lines of code. This protects against accidental exposure of the config file (git
commit, log output, email) without requiring a secret manager. The encryption key
lives separately in the environment.

### LLM client pool (lazy, cached)

**Decision:** One `LLMClient` instance per tenant, created lazily on first request
and cached for the lifetime of the process. A "default" client uses the global env
vars for tenantless requests.

**Alternatives considered:**
- *Per-request client creation*: Simple but wasteful (new HTTP connection pool per
  request).
- *Single client with per-request API key override*: The OpenAI SDK base class
  doesn't cleanly support per-request key overrides without monkey-patching.

**Rationale:** Lazy caching means zero overhead for tenants that never receive
requests, and connection pools are reused across requests for active tenants. The
pool is a simple dict keyed by tenant slug.

### Tenant resolution order

**Decision:** The middleware resolves tenant in this order:
1. JWT `org` claim (set during `/auth/token` from matched tenant slug)
2. Keycloak `groups` claim (first group matching a tenant slug)
3. Fall back to default (global env var credentials)

**Rationale:** API consumers get their tenant from the token exchange (explicit).
OIDC users get theirs from Keycloak group membership (implicit, admin-managed).
Unaffiliated users get the global default. No ambiguity, no user-facing changes.

### Keycloak groups via realm export

**Decision:** Add group definitions and a protocol mapper to `realm-export.json`
so the `groups` claim is included in JWTs automatically on fresh deployments.

**Rationale:** This is configuration, not code. Existing deployments can add groups
manually via the Keycloak admin UI. The mapper is a standard Keycloak feature.

## Tenant Config File Format

```json
{
  "tenants": {
    "faculty-a": {
      "name": "Faculty of Sciences",
      "api_secret_hash": "sha256:<hex>",
      "api_key_encrypted": "<fernet-encrypted-openrouter-key>",
      "base_url": "https://openrouter.ai/api/v1"
    },
    "faculty-b": {
      "name": "Faculty of Engineering",
      "api_secret_hash": "sha256:<hex>",
      "api_key_encrypted": "<fernet-encrypted-key>",
      "base_url": "http://ollama.internal:11434/v1"
    }
  }
}
```

Fields:
- `name`: Human-readable label (logging, debugging)
- `api_secret_hash`: SHA-256 hash of the tenant's API secret (verified with
  `hmac.compare_digest` against the hash of the incoming secret)
- `api_key_encrypted`: Fernet-encrypted LLM API key (decrypted at startup with
  `TENANT_ENCRYPTION_KEY`)
- `base_url`: Optional LLM provider URL (falls back to global `LLM_BASE_URL`)

## CLI Helper for Tenant Management

A small utility script (`scripts/manage_tenants.py`) SHALL be provided to:
- Generate a random API secret and print it (for the tenant to use)
- Hash the secret and encrypt an API key, outputting a tenant config block

This avoids manual Fernet encryption and SHA-256 hashing.

## Risks / Trade-offs

- **Tenant changes require reload**: The registry is loaded at startup. Adding or
  removing a tenant requires either a container restart or a call to the
  `POST /admin/reload-tenants` endpoint. The reload endpoint re-reads the config
  file and clears the LLM client cache. Active sessions using the old config are
  unaffected until their next LLM call.

- **Encryption key rotation**: Changing `TENANT_ENCRYPTION_KEY` requires re-encrypting
  all tenant API keys. The management script can handle this, but there's no automated
  rotation. Acceptable for PoC.

- **Keycloak group mapping is manual**: An admin must assign users to groups in
  Keycloak. There's no self-service tenant selection. This is intentional — tenant
  assignment is an administrative decision.

## Open Questions

None — all questions from the discussion have been resolved.
