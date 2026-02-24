# Change: Add Development Token Endpoint and Federated Auth Documentation

## Why

Phase 3.3 implementation revealed a critical usability gap: the API requires JWT tokens for authentication, but there's no way for developers or testers to obtain tokens. Users cannot currently test the API endpoints without manually constructing JWTs via Python code.

Additionally, the project's federated authentication approach (accepting external JWT tokens from institutional identity providers) is implemented but not documented, leaving institutions without guidance on how to integrate.

This blocks:

- Local development and testing
- API demonstrations and pilots
- Institutional integration efforts

## What Changes

1. **Development Token Endpoint** - Simple token generation for dev/testing environments

   - `POST /dev/token` endpoint (disabled in production)
   - Accepts optional `user_id` parameter
   - Returns valid JWT token with configurable expiration
   - Environment variable gating (`ENVIRONMENT != "production"`)

2. **Integration Documentation** - Clear guidance for institutional partners

   - JWT requirements and claim structure
   - Integration workflow examples
   - Testing procedures
   - OAuth 2.0/OIDC notes (Phase 5 placeholder)

3. **Testing Documentation** - Developer testing workflow
   - How to generate dev tokens
   - Example curl commands with tokens
   - Docker testing with tokens

**Breaking Changes:** None (new endpoint only, existing auth unchanged)

## What Stays the Same

- Existing JWT validation middleware (no changes)
- Session management (no changes)
- Production authentication model (federated auth via external IdP)
- API endpoints and their authentication requirements

## Impact

- **Affected specs:**
  - `specs/auth-security/spec.md` - Add dev token endpoint requirement
- **Affected code:**
  - `m_autofill/api.py` - Add `/dev/token` endpoint (~15 lines)
  - `m_shared/auth/jwt_handler.py` - Export token creation function (already exists)
- **New documentation:**

  - `docs/INTEGRATION.md` - Institutional integration guide
  - Updates to `DEPLOYMENT.md` - Testing section with token generation
  - Updates to `README.md` - Quick testing workflow

- **No new dependencies**

## Timeline

- **Estimated duration:** 2-3 days
- **Blockers:** None (independent of other work)
- **Priority:** High (blocks Phase 3.3 validation and pilot testing)
