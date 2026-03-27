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

## Notes

- MVP scope: OpenRouter only (no local LLM, no other providers)
- Required env vars: OPENROUTER_API_KEY, DEFAULT_LLM_MODEL
- Located in `m_shared/llm/client.py`
- Supports all OpenRouter available models via OpenAI-compatible API
