## ADDED Requirements

### Requirement: Per-Tenant LLM Client

The system SHALL maintain a pool of `LLMClient` instances, one per configured tenant,
each initialised with the tenant's decrypted API key and base URL. Client instances
SHALL be created lazily on first request for a given tenant and cached for the lifetime
of the process.

A default client SHALL always exist, configured from the global environment variables
(`OPENROUTER_API_KEY`, `LLM_BASE_URL`). Requests with no tenant affiliation (or from
tenants without custom LLM credentials) SHALL use the default client.

The middleware SHALL attach the resolved LLM client to the request context so that
route handlers access it transparently without tenant-aware code.

#### Scenario: Request routed to tenant LLM client

- **WHEN** a request arrives from a user with `org="faculty-a"` in their JWT
- **AND** `faculty-a` has LLM credentials in the tenant registry
- **THEN** the request uses faculty-a's LLM client (API key and base URL)

#### Scenario: Request falls back to default client

- **WHEN** a request arrives from a user with `org="default"` or no tenant match
- **THEN** the request uses the default LLM client from global environment variables

#### Scenario: Tenant client created lazily

- **WHEN** the first request for a new tenant arrives
- **THEN** a new `LLMClient` is instantiated with the tenant's credentials and cached
- **AND** subsequent requests for the same tenant reuse the cached client

#### Scenario: Route handlers unchanged

- **WHEN** a route handler accesses the LLM client via `request.app.state.llm_client`
  or equivalent
- **THEN** it receives the tenant-appropriate client without any tenant-specific code
  in the handler itself
