# Change: Setup LLM Integration (OpenRouter Client)

## Why

Both M-Chat and M-Autofill require unified access to large language models for suggestions and generation. OpenRouter provides a convenient API for accessing multiple models with a single integration point, enabling flexibility in model selection and cost management.

## What Changes

- Implement OpenRouter LLM client with OpenAI-compatible API
- Add automatic retries with exponential backoff for rate limiting and transient errors
- Support configurable model selection via environment variables
- Add token counting utility for cost estimation
- Include comprehensive unit tests for client behavior and error handling

## Impact

- Affected specs: [llm-integration](../../specs/llm-integration/spec.md)
- Affected code: `m_shared/llm/client.py` (new module)
- Dependencies: [setup-data-models](../setup-data-models/) (for request/response types)
- Downstream impact: Required by M-Autofill and M-Chat modules
- No breaking changes

## Timeline

- Estimated effort: 10-14 hours
- Milestone: Phase 1 foundation layer
