# Change: Replace institutional SSO with provider-agnostic OIDC

## Why

The current spec assumes specific institutional providers (Shibboleth, Azure AD), but the project's actual need is simpler: prove a user is *someone*, then use their stable identity as a session boundary. Who they are and where they come from does not matter — only isolation does.

## What Changes

- Replace the "OAuth 2.0 Integration" requirement with an OIDC-based approach that is provider-agnostic
- The `sub` claim from the OIDC ID token becomes the user identifier for session isolation
- Any OIDC-compliant provider works (Keycloak, Auth0, Google, Microsoft, institutional IdPs)
- Recommended deployment: self-hosted Keycloak for EU data locality and privacy-by-default
- No change to JWT validation logic — tokens are still validated as before; only issuance changes

## Impact

- Affected specs: `auth-security`
- Affected code: `m_shared/auth/oauth.py` (Phase 5 implementation), docs/integration guides
- No breaking changes to existing session isolation or JWT validation logic
