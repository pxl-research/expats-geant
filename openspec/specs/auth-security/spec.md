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

### Requirement: OAuth 2.0 Integration

The system SHALL support OAuth 2.0 for institutional SSO integration.

#### Scenario: Redirect to institutional OAuth provider

- **WHEN** a user initiates login
- **THEN** they are redirected to institutional OAuth provider (e.g., Shibboleth, Azure AD)

#### Scenario: Exchange authorization code for JWT

- **WHEN** OAuth provider returns authorization code
- **THEN** it is exchanged for JWT token usable within platform

### Requirement: Session-Based Access Control

The system SHALL enforce session isolation—users can only access their own sessions.

#### Scenario: User accesses own session

- **WHEN** a user requests data from their session
- **THEN** the request is allowed

#### Scenario: User cannot access other sessions

- **WHEN** a user attempts to access another user's session
- **THEN** the request is denied with 403 Forbidden

### Requirement: Data Encryption at Rest

The system SHALL encrypt sensitive data fields in storage.

#### Scenario: Encrypt session data

- **WHEN** session metadata is stored
- **THEN** sensitive fields (user_id, org, email) are encrypted with AES-256

#### Scenario: Decrypt on authorized access

- **WHEN** authorized user accesses session data
- **THEN** encrypted fields are decrypted transparently

### Requirement: Input Validation & Sanitization

The system SHALL validate and sanitize all user inputs.

#### Scenario: Reject malformed input

- **WHEN** invalid input is submitted (e.g., oversized prompt)
- **THEN** it is rejected with validation error

#### Scenario: Sanitize text for LLM safety

- **WHEN** user text is sent to LLM
- **THEN** it is sanitized to prevent prompt injection

## Notes

- MVP scope: JWT + institutional OAuth (no social login)
- Role-based access control (RBAC): respondent, administrator roles
- Encryption: AES-256 for sensitive fields; TLS for transport
- Located in `m_shared/auth/jwt_handler.py`, `oauth.py`
- Required env vars: JWT_SECRET, JWT_ALGORITHM, OAUTH_PROVIDER_URL
