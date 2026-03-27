## REMOVED Requirements

### Requirement: Development Token Generation Endpoint

**Reason**: The `/dev/token` endpoint has been removed from all services. It is superseded
by the production-ready `POST /auth/token` endpoint, which is available in all environments
and supports server-to-server authentication with a shared secret.

**Migration**: Use `POST /auth/token` with `user_id` and `api_secret` to obtain a JWT.
For automated tests, supply any stable unique `user_id` together with the configured
`API_SECRET`.

## ADDED Requirements

### Requirement: API Token Endpoint

The system SHALL provide a `POST /auth/token` endpoint for issuing JWTs to
server-to-server callers and anonymous API consumers. The endpoint SHALL require two
fields in the request body: a `user_id` string (caller-supplied; may be any stable unique
identifier such as a UUID, an HMAC-hash of an internal user ID, or an institutional
service-account name) and an `api_secret` string validated against the `API_SECRET`
environment variable using constant-time comparison. On success the endpoint SHALL return
a signed JWT with `org="api"` and `roles=["user"]`. The endpoint SHALL be rate-limited to
5 requests per minute per client and SHALL be publicly accessible (no prior token
required). The `API_SECRET` environment variable MUST be set to a strong random value in
all deployments.

#### Scenario: Server-to-server caller obtains JWT

- **WHEN** a backend service posts `{"user_id": "svc-account-1", "api_secret": "<correct>"}` to `POST /auth/token`
- **THEN** a signed JWT is returned containing `user_id="svc-account-1"`, `org="api"`, `roles=["user"]`
- **AND** the token is accepted in subsequent `Authorization: Bearer <token>` requests

#### Scenario: Anonymous caller uses a unique identifier

- **WHEN** an anonymous caller posts `{"user_id": "<uuid-or-hash>", "api_secret": "<correct>"}` to `POST /auth/token`
- **THEN** a JWT scoped to that `user_id` is returned
- **AND** the resulting session is fully isolated from all other sessions

#### Scenario: Reject invalid API secret

- **WHEN** a request is made with an incorrect or absent `api_secret`
- **THEN** the endpoint returns HTTP 401 Unauthorized

#### Scenario: Rate limit enforced

- **WHEN** more than 5 token requests per minute originate from the same client
- **THEN** subsequent requests within that window are rejected with HTTP 429 Too Many Requests

## MODIFIED Requirements

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
