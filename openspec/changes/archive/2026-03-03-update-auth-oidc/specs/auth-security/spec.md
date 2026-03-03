## MODIFIED Requirements

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
