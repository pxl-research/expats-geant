## MODIFIED Requirements

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

## ADDED Requirements

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
