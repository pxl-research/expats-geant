## ADDED Requirements

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
