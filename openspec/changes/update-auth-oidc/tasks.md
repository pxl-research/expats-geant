## 1. Spec Update
- [x] 1.1 Update auth-security spec (OIDC requirement)

## 2. Implementation (Phase 5)
- [ ] 2.1 Implement OIDC callback handler in `m_shared/auth/oauth.py`
- [ ] 2.2 Extract `sub` claim and map to session user_id
- [ ] 2.3 Update environment config (OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET)
- [ ] 2.4 Update integration documentation to reference OIDC instead of specific providers
- [ ] 2.5 Write unit tests for OIDC token exchange and claim extraction
- [ ] 2.6 Update docker-compose.yml with optional Keycloak service for local dev
