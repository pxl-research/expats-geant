## 1. Tenant Registry

- [x] 1.1 Create `m_shared/tenant/registry.py`: load tenants from JSON file, verify API secrets (SHA-256 + hmac.compare_digest), decrypt API keys (Fernet), return tenant config by slug
- [x] 1.2 Add `TENANT_ENCRYPTION_KEY` and `TENANT_REGISTRY_PATH` to `.env.example` (commented out, with documentation)
- [x] 1.3 Add `.secrets/` to `.gitignore`
- [x] 1.4 Write unit tests: load valid registry, missing file returns empty (single-tenant mode), missing encryption key with registry present raises error, secret verification (correct, incorrect, timing-safe), Fernet round-trip

## 2. Tenant Management Script

- [x] 2.1 Create `scripts/manage_tenants.py`: accepts tenant slug + LLM API key, generates random API secret, outputs hashed secret + encrypted key as a JSON block
- [x] 2.2 Document usage in `docs/DEPLOYMENT.md` (tenant setup section)

## 3. Auth: Multi-Tenant Secret Matching

- [x] 3.1 Update `cue_api/routes/auth.py` `/auth/token` to check incoming secret against tenant registry first, then fall back to global `API_SECRET`; set `org` claim to matched tenant slug
- [x] 3.2 Update `shape_api/routes/auth.py` with the same logic
- [x] 3.3 Write unit tests: tenant secret match sets correct org, global secret match sets org="api", no match returns 401

## 4. Auth: Keycloak Group Mapping

- [x] 4.1 Add example groups (`faculty-a`, `faculty-b`) to `keycloak/realm-export.json`
- [x] 4.2 Add a "groups" protocol mapper to the client config in `realm-export.json` (injects group memberships into JWT)
- [x] 4.3 Update `m_shared/auth/oauth.py` `exchange_code()` to read `groups` claim from ID token and resolve tenant; set `org` to matched tenant slug or `"default"`
- [x] 4.4 Write unit test: groups claim resolution (match, no match, multiple groups)

## 5. Per-Tenant LLM Client Pool

- [x] 5.1 Create LLM client pool (dict keyed by tenant slug) in startup code (`run_api.py`, `run_chat_api.py`); default client from global env vars, tenant clients created lazily from registry
- [x] 5.2 Update `m_shared/auth/middleware.py` to resolve tenant from JWT `org` claim and attach the correct LLM client to `request.state.llm_client`
- [x] 5.3 Update route handlers to use `request.state.llm_client` with fallback to `request.app.state.llm_client`; thread optional `llm_client` override through RAG pipeline entry methods
- [x] 5.4 Write unit test: correct client returned per tenant, default client for unknown tenant, lazy creation caching

## 6. Reload Endpoint

- [x] 6.1 Add `POST /admin/reload-tenants` to both `cue_api` and `shape_api` (shared `m_shared/routes/admin.py`); protected by global `API_SECRET`; re-reads registry from disk and clears LLM client cache
- [x] 6.2 Write unit test: reload with valid secret returns tenant count, reload with invalid secret returns 401, reload with no registry file returns zero tenants

## 7. Documentation and Deployment

- [x] 7.1 Add "Multi-Tenant Setup" section to `docs/DEPLOYMENT.md`: tenant registry format, encryption key setup, management script usage, reload endpoint, Keycloak group assignment
- [x] 7.2 Document the backwards-compatible default (no registry = single-tenant mode)

## 8. Testing

- [x] 8.1 Integration test: start with no tenant registry, verify system works as before (all 1011 existing tests pass)
- [x] 8.2 Integration test: start with tenant registry, obtain JWT with tenant secret, verify LLM calls use tenant credentials
- [x] 8.3 Smoke test: OIDC login with Keycloak group, verify tenant resolved in JWT
- [x] 8.4 Smoke test: add tenant to registry, call reload endpoint, verify new tenant works without restart
