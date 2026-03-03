## Context

Auth is currently JWT-only: the platform issues its own signed JWTs (via `create_token()` in
`m_shared/auth/jwt_handler.py`). For local development, `/dev/token` mints tokens directly.
No OIDC provider integration exists yet; `m_shared/auth/oauth.py` does not exist.

The goal is to allow any OIDC-compliant provider to authenticate the user, after which the
platform exchanges the provider's ID token for its own platform JWT. Everything downstream
(session middleware, session isolation, audit logging) stays unchanged.

## Goals / Non-Goals

- **Goals:**
  - Provider-agnostic OIDC authorization code flow
  - Stable `user_id` derived from `sub` claim, normalized across providers
  - Reuse existing `create_token()` and `SessionMiddleware` without modification
  - Keycloak bundled and pre-configured — zero operator setup required out of the box
  - Self-registration enabled by default — no admin account creation needed
  - Optional federation (Google, Microsoft, institutional SSO) via Keycloak admin panel
- **Non-Goals (Phase 5 only):**
  - Token refresh / silent re-authentication
  - Multi-tenant org isolation via OIDC claims
  - PKCE (can be added later)
  - SAML / non-OIDC protocols

## Decisions

### 1. Token Issuance Model

The platform validates the OIDC ID token, extracts `sub`, then calls the existing
`create_token(user_id=normalized_sub, session_id=..., org=..., roles=[...])` to issue
its own platform JWT. The client receives a platform JWT — not the OIDC token — and uses
it as a Bearer token in all subsequent API calls. `SessionMiddleware` is unchanged.

```
Browser → GET /auth/login → redirect to OIDC provider
OIDC provider → GET /auth/callback?code=...&state=... → oauth.py
oauth.py → validates code → fetches ID token → extracts sub → create_token() → platform JWT
Browser receives platform JWT → uses as Bearer token in API calls
```

### 2. Callback Endpoint

`GET /auth/callback` is added to `m_autofill/api.py` (or a shared `m_shared/auth/router.py`
if reuse across services is needed). It handles the full code exchange and returns the
platform JWT to the client.

Open question: if this endpoint is reused across services (e.g. a future m_chat service),
it should live in `m_shared/auth/router.py` and be mounted in each app's FastAPI instance.
For Phase 5 scope, adding it to `m_autofill/api.py` is sufficient.

### 3. OIDC Library

Use **`authlib`** (PyPI: `Authlib`). Reasons:
- Supports OIDC Discovery (fetches `/.well-known/openid-configuration`)
- Built-in JWKS validation and ID token verification
- Actively maintained, widely used with FastAPI/httpx
- Avoids manual JWKS fetching and JWT parsing

Add to `requirements.txt`: `Authlib>=1.3`

### 4. Sub Claim Normalization

To prevent user ID collisions across OIDC providers (e.g. Google `sub=12345` vs
Keycloak `sub=12345`), normalize as:

```python
from urllib.parse import urlparse
iss_host = urlparse(id_token_claims["iss"]).netloc  # e.g. "accounts.google.com"
user_id = f"{iss_host}:{id_token_claims['sub']}"    # e.g. "accounts.google.com:12345"
```

This produces a stable, globally unique user_id across providers.

### 5. CSRF Protection for State Parameter

Generate a random `state` value (16 bytes, URL-safe base64) on each `/auth/login` request.
Store it in a short-lived signed cookie (or in-memory dict keyed by state value with a TTL).
Validate it on `/auth/callback` before proceeding.

Simple approach for Phase 5: in-memory dict `{state: expiry_timestamp}` with a 10-minute TTL.
This works for single-instance deployments; a Redis-backed store would be needed for multi-instance.

### 6. Keycloak as Default Bundled Auth Service

Keycloak is included as a default service in `docker-compose.yml` — no profile flag needed.
Running `docker-compose up` starts the full stack including Keycloak.

A pre-configured Keycloak realm export file (`keycloak/realm-export.json`) is committed to
the repository. It is imported automatically on first startup and configures:
- A realm named `expat-geant`
- A client registered for the app (with correct redirect URIs)
- Self-registration enabled — users can create their own account on first visit
- No admin intervention required for a new deployment

**Federation (optional, operator-configured):**
Operators who want users to log in with an existing Google, Microsoft, or institutional
account can configure Keycloak's "Identity Providers" in the admin panel. This requires
registering the Keycloak instance with the external provider (one-time, ~15 minutes), but
requires no changes to the app code. Document this as an optional step in `KEYCLOAK_SETUP.md`.

Not required for running unit/integration tests (tests use a mock OIDC provider via `respx`).

### 7. Dev Token Endpoint

`POST /dev/token` is kept unchanged for local testing without OIDC infrastructure.
Disabled in production (`ENVIRONMENT=production`) as before.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `authlib` dependency | Widely adopted; adds ~500KB; well worth the correctness guarantee |
| State parameter in-memory store | Fine for single-instance; document multi-instance limitation |
| Provider-specific claim differences | Normalization function isolates this; easy to extend |
| JWKS key rotation | `authlib` handles JWKS caching and rotation automatically |

## Migration Plan

- No migration needed for existing sessions or tokens (JWT validation logic unchanged)
- `/dev/token` remains available in non-production for existing test flows
- Rollout order: deploy `oauth.py` → set OIDC env vars → point users to `/auth/login`
- Keycloak is bundled and pre-configured; `docker-compose up` is sufficient for a working deployment

## Open Questions

- Should `/auth/callback` live in `m_autofill/api.py` or `m_shared/auth/router.py`?
  (Phase 5 recommendation: `m_autofill/api.py`; revisit when a second service needs auth)
