## ADDED Requirements

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
