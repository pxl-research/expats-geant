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

## Notes

- MVP scope: OpenRouter only (no local LLM, no other providers)
- Required env vars: OPENROUTER_API_KEY, DEFAULT_LLM_MODEL
- Located in `m_shared/llm/client.py`
- Supports all OpenRouter available models via OpenAI-compatible API
