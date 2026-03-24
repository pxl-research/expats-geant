# Capability: Authentication & Security

JWT-based token authentication, OAuth 2.0 integration, and session-based access control.

## Purpose

Provide secure, session-scoped access to Cue APIs using JWT tokens. Support institutional federated authentication and enforce session isolation between users.
## Requirements
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

The system SHALL support OpenID Connect (OIDC) for provider-agnostic user authentication. The system SHALL NOT require a specific identity provider — any OIDC-compliant provider (e.g., Keycloak, Auth0, Google, Microsoft, institutional IdPs) SHALL work without code changes. The `sub` claim from the OIDC ID token SHALL be used as the stable user identifier for session isolation. The recommended self-hosted deployment option is Keycloak, for EU data locality and privacy-by-default alignment.

#### Scenario: Redirect to OIDC provider

- **WHEN** a user initiates login
- **THEN** they are redirected to the configured OIDC provider's authorization endpoint
- **AND** the provider can be any OIDC-compliant service

#### Scenario: Exchange authorization code for session token

- **WHEN** the OIDC provider returns an authorization code
- **THEN** it is exchanged for an ID token via the OIDC token endpoint
- **AND** the `sub` claim is extracted as the user identifier
- **AND** a platform JWT is issued using `sub` as `user_id` for session isolation

#### Scenario: Session isolation enforced via sub claim

- **WHEN** two users authenticate via different OIDC providers or accounts
- **THEN** their `sub` claims are distinct
- **AND** their sessions and data remain fully isolated

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

### Requirement: Development Token Generation Endpoint

The system SHALL provide a `/dev/token` endpoint for generating JWT tokens during development and testing. The endpoint SHALL be available only when the `ENVIRONMENT` variable is NOT set to "production". The endpoint SHALL accept optional parameters (`user_id`, `org`, `roles`) with sensible defaults and SHALL generate valid JWT tokens using the application's JWT_SECRET. When accessed in production mode, the endpoint SHALL return HTTP 403 Forbidden.

#### Scenario: Generate token in development mode

- **WHEN** a request is made to POST `/dev/token` with ENVIRONMENT="development"
- **AND** optional parameters `user_id="test-user"`, `org="test-org"`, `roles=["researcher"]` are provided
- **THEN** the system generates a valid JWT token with the provided claims
- **AND** returns the token with expiration information (default 1 hour)
- **AND** the token can be used to authenticate subsequent API requests

#### Scenario: Generate token with default parameters

- **WHEN** a request is made to POST `/dev/token` with no parameters
- **THEN** the system generates a JWT token with default claims: `user_id="dev-user"`, `org="dev-org"`, `roles=["user"]`
- **AND** returns the token successfully
- **AND** the token authenticates successfully with the session middleware

#### Scenario: Block token generation in production

- **WHEN** a request is made to POST `/dev/token` with ENVIRONMENT="production"
- **THEN** the system returns HTTP 403 Forbidden
- **AND** includes an error message indicating the endpoint is disabled in production
- **AND** logs a security warning about the attempted access

#### Scenario: Use generated token for authenticated requests

- **WHEN** a dev token is generated successfully
- **AND** the token is included in the Authorization header as "Bearer {token}"
- **AND** a request is made to an authenticated endpoint (e.g., POST `/upload`)
- **THEN** the SessionMiddleware validates the token
- **AND** creates an implicit session for the user
- **AND** the request proceeds successfully

### Requirement: Federated Authentication Integration Documentation

The system SHALL provide comprehensive documentation for institutional partners integrating with the Cue API using federated authentication. Documentation SHALL specify JWT token requirements including required claims (`sub`, `org`, `roles`, `exp`), token format (Bearer token in Authorization header), and recommended expiration (1-24 hours). Documentation SHALL include JWT generation examples in multiple programming languages, describe the session lifecycle and isolation model, provide troubleshooting guidance for common authentication issues, and reference planned OAuth 2.0/OIDC support in Phase 5.

#### Scenario: Institution generates JWT token

- **WHEN** an institutional partner's authentication system creates a JWT token
- **AND** the token includes required claims: `sub` (user ID), `org` (organization), `roles` (array), `exp` (expiration)
- **AND** the token is signed with the shared JWT_SECRET using HS256 algorithm
- **THEN** the documentation guides them on correct token structure
- **AND** provides example code in Python, JavaScript, and Java
- **AND** explains how to test the token with the dev token endpoint first

#### Scenario: Troubleshoot authentication failure

- **WHEN** an institution encounters authentication errors during integration
- **THEN** the documentation provides a troubleshooting section with common issues:
  - Missing or incorrect JWT_SECRET
  - Expired tokens (clock skew)
  - Missing required claims
  - Incorrect Authorization header format
- **AND** provides debugging steps with example curl commands
- **AND** explains how to verify tokens using the dev token endpoint

#### Scenario: Understand session lifecycle

- **WHEN** an institutional developer reads the integration documentation
- **THEN** they learn that sessions are created implicitly upon first authenticated request
- **AND** understand that sessions are isolated per user/organization combination
- **AND** learn how to trigger explicit session cleanup via DELETE `/session`
- **AND** understand session data persistence and cleanup policies

### Requirement: Environment-Based Configuration

The system SHALL support an `ENVIRONMENT` configuration variable with values "development", "staging", or "production" (default: "development"). This variable SHALL control the availability of development-only features such as the `/dev/token` endpoint. Production deployments SHALL explicitly set ENVIRONMENT="production" to disable development features and enforce production security policies.

#### Scenario: Deploy in development mode

- **WHEN** the system starts with ENVIRONMENT="development" (or unset)
- **THEN** the `/dev/token` endpoint is available and responds to requests
- **AND** startup logs indicate development mode is active
- **AND** development features are enabled (e.g., verbose logging, token generation)

#### Scenario: Deploy in production mode

- **WHEN** the system starts with ENVIRONMENT="production"
- **THEN** the `/dev/token` endpoint returns HTTP 403 for all requests
- **AND** startup logs indicate production mode is active
- **AND** development features are disabled for security
- **AND** only federated authentication with external tokens is supported

### Requirement: Security Event Logging

The system SHALL log security-relevant authentication events to a persistent, rotating log file (`logs/security.log`) using Python's standard `logging` module. Logging SHALL be scoped to the auth layer only (`jwt_handler.py`, `middleware.py`, `oauth.py`). Log levels SHALL reflect severity: `WARNING` for expected security failures (expired tokens, invalid state), `ERROR` for unexpected failures (provider unreachable, missing configuration), and `INFO` for successful authentication milestones. Log output SHALL NOT include sensitive values such as raw JWT strings, OIDC secrets, or unmasked subject claims.

#### Scenario: Expired token rejected by middleware

- **WHEN** a request arrives with an expired JWT
- **THEN** the middleware rejects it with 401
- **AND** a `WARNING` is written to `logs/security.log` including the request path and the reason "Token has expired"

#### Scenario: Invalid OIDC state parameter

- **WHEN** the OIDC callback receives an unknown or expired `state` parameter
- **THEN** an `OIDCStateError` is raised
- **AND** a `WARNING` is written to `logs/security.log` indicating the invalid state event

#### Scenario: ID token validation failure

- **WHEN** the OIDC ID token fails validation (wrong issuer, wrong audience, bad signature, or expired)
- **THEN** an `OIDCTokenError` is raised
- **AND** a `WARNING` is written to `logs/security.log` including the failure reason but not the raw token string

#### Scenario: OIDC provider unreachable

- **WHEN** the discovery endpoint or token endpoint cannot be reached
- **THEN** an `httpx.HTTPError` propagates
- **AND** an `ERROR` is written to `logs/security.log`

#### Scenario: Successful OIDC login

- **WHEN** a user completes the OIDC flow and a platform JWT is issued
- **THEN** an `INFO` entry is written to `logs/security.log` with the normalized `user_id`

#### Scenario: No sensitive data in logs

- **WHEN** any security event is logged
- **THEN** the log entry does not contain raw JWT strings, OIDC client secrets, or unmasked `sub` values

## Notes

- MVP scope: JWT + institutional OAuth (no social login)
- Role-based access control (RBAC): respondent, administrator roles
- Encryption: AES-256 for sensitive fields; TLS for transport
- Located in `m_shared/auth/jwt_handler.py`, `oauth.py`
- Required env vars: JWT_SECRET, JWT_ALGORITHM, OAUTH_PROVIDER_URL
