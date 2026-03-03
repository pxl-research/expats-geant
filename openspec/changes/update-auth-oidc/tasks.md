## 1. Spec Update
- [x] 1.1 Update auth-security spec (OIDC requirement)

## 2. Design
- [x] 2.0 Write design.md (OIDC flow, token model, library choice, sub normalization)

## 3. Implementation
- [ ] 3.1 Add `Authlib>=1.3` to requirements.txt
- [ ] 3.2 Implement `m_shared/auth/oauth.py`
  - [ ] 3.2a OIDC discovery — fetch provider metadata from `OIDC_ISSUER_URL/.well-known/openid-configuration`
  - [ ] 3.2b Authorization request builder — generate redirect URL + signed `state` value
  - [ ] 3.2c Authorization code exchange — POST to token endpoint, return ID token
  - [ ] 3.2d ID token validation via JWKS — verify signature, `iss`, `aud`, `exp`
  - [ ] 3.2e Sub claim normalization — `user_id = f"{iss_host}:{sub}"`
  - [ ] 3.2f Call `create_token(user_id=normalized_sub, ...)` → return platform JWT
- [ ] 3.3 Add `GET /auth/login` and `GET /auth/callback` endpoints to `m_autofill/api.py`
  - [ ] 3.3a `/auth/login` — build OIDC redirect URL, set state cookie, return redirect
  - [ ] 3.3b `/auth/callback` — validate state, exchange code, return platform JWT
  - [ ] 3.3c Error handling — invalid code, expired state, provider error → 400/502
- [ ] 3.4 Update environment config
  - [ ] 3.4a Add `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` to `.env.example` with descriptions
  - [ ] 3.4b Load and validate OIDC vars in `oauth.py` (fail fast if missing in production)
- [ ] 3.5 Export new oauth functions from `m_shared/auth/__init__.py`

## 4. Tests
- [ ] 4.1 Unit tests in `tests/test_oauth.py`
  - [ ] 4.1a OIDC discovery fetch — success and unreachable provider (mock HTTP with respx)
  - [ ] 4.1b Authorization code exchange — success case
  - [ ] 4.1c ID token validation — valid, expired, wrong audience, bad signature
  - [ ] 4.1d Sub claim normalization — multiple providers produce distinct user_ids
  - [ ] 4.1e Missing OIDC env vars — raise clear ConfigurationError
- [ ] 4.2 Integration test — full OIDC flow with mock provider (respx mock of token + JWKS endpoints)

## 5. Keycloak Setup
- [ ] 5.1 Add Keycloak as a default service in `docker-compose.yml` (no profile flag required)
- [ ] 5.2 Create `keycloak/realm-export.json` — pre-configured realm imported on first startup
  - [ ] 5.2a Realm: `expat-geant`
  - [ ] 5.2b Client registered with correct redirect URIs for the app
  - [ ] 5.2c Self-registration enabled by default
- [ ] 5.3 Document optional federation in `docs/KEYCLOAK_SETUP.md`
  - [ ] 5.3a Keycloak image version, port, initial admin credentials
  - [ ] 5.3b How to connect Google as an identity provider (optional)
  - [ ] 5.3c How to connect Microsoft/Azure AD as an identity provider (optional)
  - [ ] 5.3d How to connect institutional SSO/LDAP as an identity provider (optional)

## 6. Documentation
- [ ] 6.1 Update `docs/INTEGRATION.md` — replace specific provider references (Shibboleth, Azure AD) with provider-agnostic OIDC guide
- [ ] 6.2 Update `m_shared/README.md` — reflect that `auth/oauth.py` now exists and document its public API
