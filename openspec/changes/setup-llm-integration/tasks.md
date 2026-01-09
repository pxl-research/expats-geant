# Implementation Tasks: setup-llm-integration

## 1. OpenRouter Client Implementation

- [x] 1.1 Create `m_shared/llm/__init__.py` with module exports
- [x] 1.2 Implement OpenRouterClient class with OpenAI-compatible API
- [x] 1.3 Add environment variable configuration (OPENROUTER_API_KEY, DEFAULT_LLM_MODEL)
- [x] 1.4 Implement generate() method for single completion requests
- [x] 1.5 Implement batch_generate() method for multiple requests
- [x] 1.6 Add model parameter override support

## 2. Resilience & Retry Logic

- [x] 2.1 Implement exponential backoff for rate limiting (429 errors)
- [x] 2.2 Implement retry logic for transient errors (5xx)
- [x] 2.3 Add configurable max_retries and backoff parameters
- [x] 2.4 Log retry attempts and failures for debugging

## 3. Generation Parameters

- [x] 3.1 Support temperature parameter for output determinism
- [x] 3.2 Support max_tokens parameter for response length control
- [ ] 3.3 Support top_p and other sampling parameters
- [ ] 3.4 Create sensible defaults for common use cases

## 4. Token Counting

- [x] 4.1 Implement token_count() utility function
- [x] 4.2 Use tiktoken for accurate token counting
- [x] 4.3 Integrate with LLM client for cost estimation

## 5. Unit Tests

- [x] 5.1 Create `tests/test_llm_client.py`
- [x] 5.2 Test successful generation requests
- [x] 5.3 Test rate limiting and retry behavior
- [x] 5.4 Test parameter passing and model override
- [x] 5.5 Test token counting accuracy
- [x] 5.6 Test error handling for invalid API key
- [x] 5.7 Run tests and verify 100% passing

## 6. Documentation

- [x] 6.1 Add docstrings and type hints to all methods
- [x] 6.2 Document environment variable requirements
- [x] 6.3 Include usage examples in module docstring
