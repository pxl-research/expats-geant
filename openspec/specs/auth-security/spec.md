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

The system SHALL enforce session isolation — users can only access sessions within their
own user directory. Session directories SHALL be nested under a user-scoped folder
derived from `sha256(user_id)[:16]`. The middleware SHALL verify that the requested
session exists under the authenticated user's folder.

#### Scenario: User accesses own session

- **WHEN** a user requests data from a session within their user folder
- **THEN** the request is allowed

#### Scenario: User cannot access other users' sessions

- **WHEN** a user attempts to access a session that exists under a different user's folder
- **THEN** the request is denied with 403 Forbidden

#### Scenario: Session-less token accesses session list

- **WHEN** a user authenticates with a JWT that has `session_id=null`
- **THEN** only session management endpoints (`GET /sessions`, `POST /sessions/*/select`, `POST /sessions/*/transfer`) are accessible
- **AND** all session-scoped endpoints return 400 Bad Request

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

The system SHALL support an `ENVIRONMENT` configuration variable with values
"development", "staging", or "production" (default: "development"). This variable SHALL
control environment-specific behaviour such as log verbosity and security policy
enforcement. Production deployments SHALL explicitly set `ENVIRONMENT="production"` to
enforce production security policies.

#### Scenario: Deploy in development mode

- **WHEN** the system starts with `ENVIRONMENT="development"` (or unset)
- **THEN** startup logs indicate development mode is active
- **AND** verbose logging and development-oriented features are enabled

#### Scenario: Deploy in production mode

- **WHEN** the system starts with `ENVIRONMENT="production"`
- **THEN** startup logs indicate production mode is active
- **AND** only production-hardened authentication paths (`POST /auth/token`, OIDC) are active

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

### Requirement: API Token Endpoint

The system SHALL provide a `POST /auth/token` endpoint for issuing JWTs to
server-to-server callers and anonymous API consumers. The endpoint SHALL require two
fields in the request body: a `user_id` string (caller-supplied; may be any stable unique
identifier such as a UUID, an HMAC-hash of an internal user ID, or an institutional
service-account name) and an `api_secret` string. The endpoint SHALL accept an optional
`session_id` field to resume an existing session.

When a tenant registry is configured, the endpoint SHALL match the provided `api_secret`
against all tenant API secret hashes using constant-time comparison. On match, the
issued JWT SHALL contain `org` set to the tenant slug. When no tenant matches but the
secret matches the global `API_SECRET`, the JWT SHALL contain `org="api"` (default
behaviour). When no match is found, the endpoint SHALL return 401 Unauthorized.

When no tenant registry is configured, the endpoint SHALL validate against the global
`API_SECRET` as before.

When `session_id` is omitted, the endpoint SHALL create a new session under the user's
folder and include the new session_id in the JWT. When `session_id` is provided, the
endpoint SHALL verify the session exists under the user's folder and include it in the
JWT; if the session does not exist or belongs to another user, the endpoint SHALL return
404 Not Found.

The endpoint SHALL be rate-limited to 5 requests per minute per client and SHALL be
publicly accessible (no prior token required). The `API_SECRET` environment variable
MUST be set to a strong random value in all deployments.

#### Scenario: Server-to-server caller obtains JWT

- **WHEN** a backend service posts `{"user_id": "svc-account-1", "api_secret": "<correct>"}` to `POST /auth/token`
- **THEN** a signed JWT is returned containing `user_id="svc-account-1"`, `org="api"`, `roles=["user"]`
- **AND** a new session is created under the user's folder
- **AND** the token is accepted in subsequent `Authorization: Bearer <token>` requests

#### Scenario: Tenant-specific caller obtains JWT

- **WHEN** a caller posts an `api_secret` that matches tenant `faculty-a`
- **THEN** the issued JWT contains `org="faculty-a"`
- **AND** subsequent requests using this token are routed to faculty-a's LLM credentials

#### Scenario: Anonymous caller uses a unique identifier

- **WHEN** an anonymous caller posts `{"user_id": "<uuid-or-hash>", "api_secret": "<correct>"}` to `POST /auth/token`
- **THEN** a JWT scoped to that `user_id` is returned with a new session
- **AND** the resulting session is fully isolated from all other sessions

#### Scenario: Resume existing session

- **WHEN** a caller posts `{"user_id": "svc-account-1", "api_secret": "<correct>", "session_id": "abc123"}` to `POST /auth/token`
- **AND** session `abc123` exists under the user's folder
- **THEN** a JWT scoped to that session is returned

#### Scenario: Resume non-existent session

- **WHEN** a caller provides a `session_id` that does not exist under their user folder
- **THEN** the endpoint returns HTTP 404 Not Found

#### Scenario: Reject invalid API secret

- **WHEN** a request is made with an incorrect or absent `api_secret`
- **THEN** the endpoint returns HTTP 401 Unauthorized

#### Scenario: Rate limit enforced

- **WHEN** more than 5 token requests per minute originate from the same client
- **THEN** subsequent requests within that window are rejected with HTTP 429 Too Many Requests

### Requirement: Tenant Resolution via Keycloak Groups

OIDC-authenticated users SHALL be associated with a tenant when their JWT contains a
`groups` claim with a value matching a tenant slug in the registry. The Keycloak realm
configuration SHALL include a protocol mapper that injects the user's group memberships
into the `groups` claim of the ID token.

When a user belongs to multiple groups, the first group matching a tenant slug SHALL be
used. When no group matches, the user falls back to the global default credentials.

#### Scenario: OIDC user in tenant group

- **WHEN** a user authenticates via OIDC and their Keycloak groups include `faculty-a`
- **AND** `faculty-a` is a registered tenant
- **THEN** the platform JWT is issued with `org="faculty-a"`
- **AND** subsequent requests use faculty-a's LLM credentials

#### Scenario: OIDC user without tenant group

- **WHEN** a user authenticates via OIDC and has no groups matching a tenant slug
- **THEN** the platform JWT is issued with `org="default"`
- **AND** subsequent requests use the global LLM credentials

#### Scenario: Keycloak groups claim included in JWT

- **WHEN** a user authenticates through the bundled Keycloak instance
- **THEN** the ID token includes a `groups` claim listing the user's group memberships

### Requirement: Session Listing

The system SHALL provide a `GET /sessions` endpoint that returns all active (non-expired)
sessions for the authenticated user. The session list SHALL be derived from the
filesystem by scanning the user's session directory. Each entry SHALL include the
session_id, a human-readable label (from survey metadata if available), created_at
timestamp, and session status.

#### Scenario: User with active sessions

- **WHEN** an authenticated user calls `GET /sessions`
- **THEN** all non-expired sessions under their user folder are returned
- **AND** each entry includes session_id, label, created_at, and status

#### Scenario: User with no sessions

- **WHEN** an authenticated user calls `GET /sessions` and has no active sessions
- **THEN** an empty list is returned

### Requirement: Session Transfer

The system SHALL provide a `POST /sessions/{session_id}/transfer` endpoint that moves
a session from the caller's user folder to a recipient's user folder. The recipient
MUST have logged in at least once (their user folder must exist). On successful transfer,
the session's `metadata.json` SHALL be updated with the new owner's `user_id`. The
caller's JWT is no longer valid for the transferred session.

#### Scenario: Successful transfer

- **WHEN** User A calls `POST /sessions/{session_id}/transfer` with `{"recipient_user_id": "user-b"}`
- **AND** User B's user folder exists
- **THEN** the session directory is moved from User A's folder to User B's folder
- **AND** `metadata.json` is updated with User B's user_id
- **AND** User A can no longer access the session

#### Scenario: Recipient has not logged in

- **WHEN** User A attempts to transfer a session to a user whose folder does not exist
- **THEN** the endpoint returns HTTP 404 Not Found with detail indicating the recipient must log in first

#### Scenario: Transfer non-owned session

- **WHEN** a user attempts to transfer a session they do not own
- **THEN** the endpoint returns HTTP 403 Forbidden

### Requirement: User Data Deletion (RTBF)

The system SHALL provide a mechanism to delete all session data for a user by removing
their entire user directory (`data/sessions/{user_hash}/`). This supports the GDPR
Right to Be Forgotten.

#### Scenario: Delete all user data

- **WHEN** a user data deletion is requested for a given user_id
- **THEN** the entire user directory and all contained sessions are removed
- **AND** all associated vector stores, documents, and audit data are deleted

## Notes

- MVP scope: JWT + institutional OAuth (no social login)
- Role-based access control (RBAC): respondent, administrator roles
- Encryption: AES-256 for sensitive fields; TLS for transport
- Located in `m_shared/auth/jwt_handler.py`, `oauth.py`
- Required env vars: JWT_SECRET, JWT_ALGORITHM, OAUTH_PROVIDER_URL
