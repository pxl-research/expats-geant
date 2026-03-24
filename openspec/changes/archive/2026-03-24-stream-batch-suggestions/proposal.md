# Change: Stream batch suggestions via SSE

## Why

The current batch suggestion flow blocks the entire HTTP connection until every question
has been processed by the LLM. For surveys with more than ~8 questions, this exceeds
the 60-second m-ui timeout (temporarily raised to 300s as a workaround), leaving the
respondent staring at a spinner with no feedback. The root cause is architectural: all
results are accumulated server-side before any response is sent.

Streaming allows each suggestion to be delivered to the browser the moment it is ready,
eliminating the timeout problem and giving respondents immediate, progressive feedback.

## What Changes

- **m-autofill**: Add `POST /suggest/stream` SSE endpoint that emits one JSON event per
  suggestion as each LLM call completes, rather than waiting for all questions to finish.
  The existing `POST /suggest/batch` endpoint is retained unchanged for API clients that
  prefer a single JSON response.
- **m-autofill**: Wrap the synchronous LLM call inside `asyncio.run_in_executor` so the
  event loop is not blocked while waiting for the LLM API, allowing m-autofill to serve
  other requests concurrently during generation.
- **m-ui**: Replace the current `GET /session/{id}/suggest` bulk-load endpoint with a
  `GET /session/{id}/suggest-stream` SSE proxy that forwards the m-autofill stream,
  injecting auth headers and re-rendering each event as HTML via the existing
  `suggestion_block.html` partial.
- **m-ui**: Update `survey.html` to use `hx-ext="sse"` instead of `hx-trigger="load"`,
  connecting to the new stream endpoint. Each streamed suggestion block uses
  `hx-swap-oob` to place itself directly into the correct question zone without
  additional JavaScript.

## Impact

- Affected specs: `answer-suggestion`, `survey-ui`
- Affected code:
  - `m_autofill/api.py` — new `/suggest/stream` endpoint
  - `m_autofill/rag_pipeline.py` — suggest_batch refactored to async generator
  - `m_ui/router.py` — new SSE proxy, remove old suggest_partial
  - `m_ui/api_client.py` — remove batch_suggest, add stream helper
  - `m_ui/templates/survey.html` — hx-ext="sse" wiring
  - `m_ui/templates/partials/suggestion_block.html` — add hx-swap-oob attribute
- No breaking change to `POST /suggest/batch` — existing API clients unaffected
- Revert the temporary 300s timeout workaround in `m_ui/api_client.py`
