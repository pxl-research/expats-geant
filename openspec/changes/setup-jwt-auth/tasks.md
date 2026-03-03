# Implementation Tasks: setup-jwt-auth

## 1. JWT Token Handler Implementation

- [x] 1.1 Create `m_shared/auth/__init__.py` with module exports
- [x] 1.2 Implement create_token() function with user_id, session_id, org, and roles claims
- [x] 1.3 Implement validate_token() function with signature and expiration checks
- [x] 1.4 Add environment variable configuration (JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS)
- [x] 1.5 Implement verify_session_access() for session isolation
- [ ] 1.6 _(Superseded)_ Token refresh for extended sessions — with OIDC in place, Keycloak manages refresh tokens natively; when the platform JWT expires the user re-authenticates via `/auth/login → /auth/callback` which issues a fresh one; no separate refresh endpoint is needed

## 2. Session-Based Access Control

- [x] 2.1 Implement session_id claim validation
- [x] 2.2 Implement verify_session_access() function for session isolation (403 on unauthorized)
- [x] 2.3 Add user_id claim validation
- [x] 2.4 Include roles claim in token for future RBAC support
- [x] 2.5 `SessionMiddleware` implemented in `m_shared/auth/middleware.py` — validates Bearer JWT, lazy-creates/reuses session, attaches `request.state.session` and `request.state.claims` for downstream handlers; OIDC endpoints (`/auth/login`, `/auth/callback`) whitelisted as public; registered in `run_api.py`; tested in `tests/test_session_api.py`

## 3. Input Validation & Sanitization

- [x] 3.1 Create `m_shared/auth/validators.py`
- [x] 3.2 Implement validate_input_size() for size checks
- [x] 3.3 Implement sanitize_text() for HTML escaping and control character removal
- [x] 3.4 Implement validate_and_sanitize() convenience function
- [x] 3.5 Add protection against XSS and prompt injection

## 4. Error Handling

- [x] 4.1 Create custom exceptions (TokenExpiredError, TokenInvalidError, ValidationError)
- [x] 4.2 Raise PermissionError for 403 Forbidden cases (session access)
- [x] 4.3 Provide clear error messages for debugging
- [ ] 4.4 _(Future)_ Structured security event logging — currently no logging in `jwt_handler.py`, `middleware.py`, or `oauth.py`; events to capture: expired/invalid tokens (middleware), session rejections, invalid OIDC state parameter, ID token validation failures, OIDC provider unreachable; low effort (~1 day: add `logging` calls + log-capture tests)

## 5. Unit Tests

- [x] 5.1 Create `tests/test_auth.py` (19 tests for JWT)
- [x] 5.2 Test token creation with various claims (roles, org, custom expiration)
- [x] 5.3 Test token validation with valid/invalid signatures
- [x] 5.4 Test expiration checking (TokenExpiredError)
- [x] 5.5 Test session isolation (verify_session_access)
- [x] 5.6 Create `tests/test_validators.py` (27 tests for validation)
- [x] 5.7 Test input size validation and sanitization
- [x] 5.8 Test XSS prevention and control character removal
- [x] 5.9 Test error handling and custom exceptions
- [x] 5.10 Run tests and verify 100% passing (46/46 tests pass)

## 6. Documentation

- [x] 6.1 Add comprehensive docstrings to all functions
- [x] 6.2 Document JWT claims structure (user_id, session_id, org, roles, iat, exp)
- [x] 6.3 Update .env.example with JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
- [x] 6.4 Include usage examples in docstrings
