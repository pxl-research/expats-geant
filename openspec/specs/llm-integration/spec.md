# Capability: LLM Integration

## Purpose

Unified interface for accessing large language models via OpenRouter (MVP) with environment-based configuration.
## Requirements
### Requirement: OpenRouter Client

The system SHALL provide a unified LLM client that sends requests to OpenRouter with API key authentication.

#### Scenario: Successful LLM generation request

- **WHEN** a generation request is made with prompt and model name
- **THEN** the client sends request to OpenRouter and returns completion text

#### Scenario: Rate limiting and retries

- **WHEN** OpenRouter returns rate limit or transient error
- **THEN** the client automatically retries with exponential backoff

### Requirement: Model Configuration

The system SHALL support configurable LLM model selection via environment variables.

#### Scenario: Model selection from environment

- **WHEN** LLM client initializes
- **THEN** it reads DEFAULT_LLM_MODEL from environment and uses it for requests

#### Scenario: Model override per request

- **WHEN** a request specifies a different model name
- **THEN** that model is used instead of the default

### Requirement: Temperature and Parameters

The system SHALL support temperature and other generation parameters for LLM requests.

#### Scenario: Custom temperature for suggestion generation

- **WHEN** a suggestion request specifies temperature=0.7
- **THEN** the request uses that temperature for more deterministic output

### Requirement: Token Counting

The system SHALL provide token counting utility to estimate prompt and completion tokens.

#### Scenario: Token estimation for prompt

- **WHEN** token_count() is called with a prompt
- **THEN** it returns estimated token count for that prompt

### Requirement: Extended Thinking Budget

The system SHALL support an optional extended-thinking budget for LLM requests. When
enabled, the client SHALL inject `{"thinking": {"type": "enabled", "budget_tokens": N}}`
into the `extra_body` of each request, where `N` is the configured token budget. The
budget SHALL be configurable via the `THINKING_BUDGET_TOKENS` environment variable (parsed
as an integer) or overridden per-client instance via the `thinking_budget` constructor
parameter. When neither is set, extended thinking SHALL be disabled. Extended thinking is
only effective with models that support it (Claude 3.5+ / 4.x series via OpenRouter).

#### Scenario: Thinking budget enabled via environment variable

- **WHEN** `THINKING_BUDGET_TOKENS=8000` is set and the LLM client is initialised
- **THEN** every completion request includes `extra_body={"thinking": {"type": "enabled", "budget_tokens": 8000}}`
- **AND** the model returns extended reasoning alongside its answer

#### Scenario: Thinking budget disabled by default

- **WHEN** neither `THINKING_BUDGET_TOKENS` nor the constructor parameter is set
- **THEN** no thinking configuration is added to requests
- **AND** the model behaves with standard (non-extended) output

#### Scenario: Per-instance override

- **WHEN** `LLMClient(thinking_budget=4000)` is constructed explicitly
- **THEN** that instance uses `budget_tokens=4000` regardless of the environment variable

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

### Requirement: Tool Call Return Access

The LLM client SHALL expose a completion method that returns the full response
message — both textual content and any tool calls — so that callers
implementing a tool-call loop can dispatch tool invocations and continue the
conversation. The existing content-only completion method SHALL remain
available for backwards compatibility with callers that do not use tools.

The method SHALL accept a `tools` parameter per call so that different
endpoints can advertise different tool surfaces against a shared `LLMClient`
instance without mutating the client's default `tools_list`.

The retry, backoff, headers, temperature, and extended-thinking behaviours
that apply to the content-only completion SHALL also apply to the new method.

#### Scenario: Text-only response returned

- **WHEN** the new method is called and the model returns a message with
  content and no tool calls
- **THEN** the method SHALL return a result whose content is the model text
- **AND** whose tool-call list is empty

#### Scenario: Tool call surfaced to the caller

- **WHEN** the new method is called and the model returns a message containing
  a tool call
- **THEN** the method SHALL return a result whose tool-call list contains the
  call's name, arguments, and call identifier
- **AND** the caller SHALL be able to dispatch the call and append a tool
  result message before the next iteration

#### Scenario: Per-call tools override

- **WHEN** the new method is called with an explicit `tools` argument
- **THEN** that tool list SHALL be sent to the model for that call only
- **AND** the client's default `tools_list` SHALL NOT be mutated

## Notes

- MVP scope: OpenRouter only (no local LLM, no other providers)
- Required env vars: OPENROUTER_API_KEY, DEFAULT_LLM_MODEL
- Located in `m_shared/llm/client.py`
- Supports all OpenRouter available models via OpenAI-compatible API
