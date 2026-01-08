# Capability: Authentication & Security

JWT-based token authentication, OAuth 2.0 integration, and session-based access control.

## ADDED Requirements

### Requirement: JWT Token Generation

The system SHALL create signed JWT tokens for authenticated session access.

#### Scenario: Create token for user session

- **WHEN** a user initiates a session
- **THEN** a JWT token is generated containing user_id, org, roles, and expiration

#### Scenario: Include session metadata in token

- **WHEN** a token is generated
- **THEN** it includes session_id claim for session-scoped authorization

### Requirement: JWT Token Validation

The system SHALL verify JWT tokens on each request requiring authentication.

#### Scenario: Validate token on API request

- **WHEN** a request includes a JWT token
- **THEN** the token is validated for signature, expiration, and claims

#### Scenario: Reject expired or invalid tokens

- **WHEN** a token is expired or tampered with
- **THEN** the request is rejected with 401 Unauthorized

### Requirement: Session-Based Access Control

The system SHALL enforce session isolation—users can only access their own sessions.

#### Scenario: User accesses own session

- **WHEN** a user requests data from their session
- **THEN** the request is allowed

#### Scenario: User cannot access other sessions

- **WHEN** a user attempts to access another user's session
- **THEN** the request is denied with 403 Forbidden

### Requirement: Input Validation & Sanitization

The system SHALL validate and sanitize all user inputs.

#### Scenario: Reject malformed input

- **WHEN** invalid input is submitted (e.g., oversized prompt)
- **THEN** it is rejected with validation error

#### Scenario: Sanitize text for LLM safety

- **WHEN** user text is sent to LLM
- **THEN** it is sanitized to prevent prompt injection

## DEFERRED Requirements

The following auth requirements are deferred to Phase 5 (Integration & Pilot):

- OAuth 2.0 Integration
- Data Encryption at Rest
- Role-based access control (RBAC) beyond basic support

## Notes

- MVP scope (Phase 1): JWT token generation/validation + basic session isolation + input validation
- OAuth 2.0 deferred to Phase 5 when institutional SSO needed
- Role-based access control (RBAC): respondent, administrator roles (basic support in Phase 1)
- Located in `m_shared/auth/jwt_handler.py`, `m_shared/utils/validators.py`
- Required env vars: JWT_SECRET, JWT_ALGORITHM
