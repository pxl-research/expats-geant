# Change: Setup JWT Authentication

## Why

Secure access to both M-Chat and M-Autofill requires authentication and session management. JWT tokens provide stateless, scalable authentication while supporting institutional SSO in later phases. Phase 1 focuses on core JWT creation and validation; OAuth 2.0 integration comes in Phase 5.

## What Changes

- Implement JWT token generation with user and session claims
- Implement JWT token validation with signature and expiration checks
- Add session-based access control to enforce user isolation
- Include input validation utilities for LLM safety
- Add comprehensive unit tests for token lifecycle and error cases

## Impact

- Affected specs: [auth-security](../../specs/auth-security/spec.md)
- Affected code: `m_shared/auth/jwt_handler.py`, `m_shared/utils/validators.py` (new modules)
- Dependencies: [setup-data-models](../setup-data-models/) (for Session model)
- Downstream impact: Required by M-Autofill and M-Chat API layers
- Breaking changes: None (initial implementation)

## Timeline

- Estimated effort: 8-12 hours
- Milestone: Phase 1 foundation layer
- Note: OAuth 2.0 integration deferred to Phase 5
