## ADDED Requirements

### Requirement: Tenant Registry

The system SHALL support an optional tenant registry loaded from a JSON config file at
startup. Each tenant entry SHALL contain: a slug (unique identifier), a human-readable
name, a SHA-256 hash of the tenant's API secret, a Fernet-encrypted LLM API key, and
an optional LLM base URL.

The registry file SHALL be stored outside the codebase (mounted volume or `.secrets/`
directory). When no registry file is present, the system SHALL operate in single-tenant
mode using the global `API_SECRET` and `OPENROUTER_API_KEY` from the environment.

LLM API keys SHALL be encrypted at rest using Fernet symmetric encryption with a
server-side `TENANT_ENCRYPTION_KEY` environment variable. API secrets SHALL be stored
as SHA-256 hashes and verified using constant-time comparison.

#### Scenario: System starts with tenant registry

- **WHEN** a valid tenant registry file is present and `TENANT_ENCRYPTION_KEY` is set
- **THEN** the system loads all tenant configurations at startup
- **AND** decrypts LLM API keys into memory for runtime use

#### Scenario: System starts without tenant registry

- **WHEN** no tenant registry file is present
- **THEN** the system operates in single-tenant mode using global environment variables
- **AND** behaves identically to a deployment without tenant support

#### Scenario: Missing encryption key with registry present

- **WHEN** a tenant registry file is present but `TENANT_ENCRYPTION_KEY` is not set
- **THEN** the system refuses to start and logs a clear error message

### Requirement: Tenant Management Script

The system SHALL provide a CLI utility script (`scripts/manage_tenants.py`) for
generating tenant credentials. The script SHALL generate a random API secret, compute
its SHA-256 hash, encrypt a provided LLM API key with Fernet, and output a
ready-to-use tenant config block.

#### Scenario: Generate tenant credentials

- **WHEN** an operator runs the management script with a tenant slug and LLM API key
- **THEN** the script outputs a JSON block containing the hashed secret, encrypted key,
  and the plaintext API secret (displayed once, for the tenant to store)

### Requirement: Tenant Registry Reload Endpoint

The system SHALL provide a `POST /admin/reload-tenants` endpoint that re-reads the
tenant registry from disk and replaces the in-memory tenant configuration without
restarting the service. The endpoint SHALL also clear the per-tenant LLM client cache
so that new or updated tenant credentials take effect on the next request.

The endpoint SHALL be protected by the global `API_SECRET` (provided in the request
body or as a bearer token). It SHALL return a summary of the reload result (number of
tenants loaded).

When no tenant registry file is present, the endpoint SHALL return a success response
indicating zero tenants loaded (single-tenant mode).

#### Scenario: Reload after adding a tenant

- **WHEN** an operator adds a new tenant to the registry file and calls
  `POST /admin/reload-tenants` with a valid `API_SECRET`
- **THEN** the new tenant is available immediately without restarting the service
- **AND** the response indicates the number of tenants loaded

#### Scenario: Reload with invalid secret

- **WHEN** `POST /admin/reload-tenants` is called with an incorrect or missing secret
- **THEN** the endpoint returns HTTP 401 Unauthorized

#### Scenario: Reload with no registry file

- **WHEN** `POST /admin/reload-tenants` is called but no registry file exists
- **THEN** the endpoint returns success with zero tenants loaded
- **AND** the system continues in single-tenant mode

## MODIFIED Requirements

### Requirement: API Token Endpoint

The system SHALL provide a `POST /auth/token` endpoint for issuing JWTs to
server-to-server callers and anonymous API consumers. The endpoint SHALL require two
fields in the request body: a `user_id` string (caller-supplied; may be any stable unique
identifier such as a UUID, an HMAC-hash of an internal user ID, or an institutional
service-account name) and an `api_secret` string.

When a tenant registry is configured, the endpoint SHALL match the provided `api_secret`
against all tenant API secret hashes using constant-time comparison. On match, the
issued JWT SHALL contain `org` set to the tenant slug. When no tenant matches but the
secret matches the global `API_SECRET`, the JWT SHALL contain `org="api"` (default
behaviour). When no match is found, the endpoint SHALL return 401 Unauthorized.

When no tenant registry is configured, the endpoint SHALL validate against the global
`API_SECRET` as before.

The endpoint SHALL be rate-limited to 5 requests per minute per client and SHALL be
publicly accessible (no prior token required). The `API_SECRET` environment variable
MUST be set to a strong random value in all deployments.

#### Scenario: Server-to-server caller obtains JWT

- **WHEN** a backend service posts `{"user_id": "svc-account-1", "api_secret": "<correct>"}` to `POST /auth/token`
- **THEN** a signed JWT is returned containing `user_id="svc-account-1"`, `org="api"`, `roles=["user"]`
- **AND** the token is accepted in subsequent `Authorization: Bearer <token>` requests

#### Scenario: Tenant-specific caller obtains JWT

- **WHEN** a caller posts an `api_secret` that matches tenant `faculty-a`
- **THEN** the issued JWT contains `org="faculty-a"`
- **AND** subsequent requests using this token are routed to faculty-a's LLM credentials

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

## ADDED Requirements

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
