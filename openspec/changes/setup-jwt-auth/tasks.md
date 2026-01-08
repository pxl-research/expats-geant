# Implementation Tasks: setup-jwt-auth

## 1. JWT Token Handler Implementation

- [ ] 1.1 Create `m_shared/auth/__init__.py` with module exports
- [ ] 1.2 Create JWTHandler class with configuration from environment
- [ ] 1.3 Implement create_token() method with user_id, session_id, org, and roles claims
- [ ] 1.4 Implement validate_token() method with signature and expiration checks
- [ ] 1.5 Implement token refresh logic for extended sessions
- [ ] 1.6 Add secure secret key generation and storage guidance

## 2. Session-Based Access Control

- [ ] 2.1 Implement session_id claim validation
- [ ] 2.2 Create session isolation decorator for API endpoints
- [ ] 2.3 Add user_id claim validation
- [ ] 2.4 Implement role-based access control (RBAC) support

## 3. Input Validation & Sanitization

- [ ] 3.1 Create `m_shared/utils/validators.py`
- [ ] 3.2 Implement input_validator() for size/format checks
- [ ] 3.3 Implement sanitize_for_llm() to prevent prompt injection
- [ ] 3.4 Add regex patterns for common validation rules

## 4. Error Handling

- [ ] 4.1 Create custom exceptions (TokenExpiredError, InvalidTokenError, ValidationError)
- [ ] 4.2 Implement proper error responses with 401/403 status codes
- [ ] 4.3 Log security events (failed validations, rejections)

## 5. Unit Tests

- [ ] 5.1 Create `tests/test_jwt_handler.py`
- [ ] 5.2 Test token creation with various claims
- [ ] 5.3 Test token validation with valid/invalid signatures
- [ ] 5.4 Test expiration checking
- [ ] 5.5 Test session isolation (user cannot access other sessions)
- [ ] 5.6 Test input validation and sanitization
- [ ] 5.7 Test error handling and custom exceptions
- [ ] 5.8 Run tests and verify 100% passing

## 6. Documentation

- [ ] 6.1 Add docstrings to all methods
- [ ] 6.2 Document JWT claims structure
- [ ] 6.3 Document environment variable requirements (JWT_SECRET, JWT_ALGORITHM)
- [ ] 6.4 Include usage examples in module docstring
