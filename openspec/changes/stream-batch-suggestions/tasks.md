## 1. m-autofill: Async generator + streaming endpoint

- [x] 1.1 Refactor `rag_pipeline.suggest_batch` into an async generator `suggest_batch_stream`
      that yields one result dict per question using `asyncio.run_in_executor` for the LLM call
- [x] 1.2 Add `POST /suggest/stream` endpoint in `m_autofill/api.py` returning
      `StreamingResponse` (`text/event-stream`) that consumes the generator and emits
      `event: suggestion` per item and `event: done` on completion
- [x] 1.3 Set `X-Accel-Buffering: no` and `Cache-Control: no-cache` on the streaming response
- [x] 1.4 Keep `POST /suggest/batch` and `suggest_batch` unchanged

## 2. m-autofill: Harden per-item error handling

- [x] 2.1 In `suggest_batch_stream`, catch `Exception` (not just `RuntimeError`) around the
      LLM call so that `openai.APIError` and other non-runtime errors emit a degraded
      suggestion rather than terminating the stream

## 3. m-ui: SSE proxy endpoint

- [x] 3.1 Add `GET /session/{session_id}/suggest-stream` to `m_ui/router.py` that opens an
      `httpx` streaming POST to `{AUTOFILL_API_URL}/suggest/stream` with auth headers and the
      survey items as body
- [x] 3.2 For each `event: suggestion` received, render `suggestion_block.html` with
      `hx-swap-oob="true"` and `id="sug-{item_id}"` set, then forward as an SSE event
- [x] 3.3 Forward the `event: done` event to signal stream completion
- [x] 3.4 On stream error, emit a final `event: error` event with a user-facing message
- [x] 3.5 Remove the old `GET /session/{session_id}/suggest` endpoint and `batch_suggest`
      from `m_ui/api_client.py`

## 4. m-ui: Frontend wiring

- [x] 4.1 Update `m_ui/templates/survey.html` to replace `hx-trigger="load"` bulk container
      with `hx-ext="sse"` / `sse-connect="/session/{id}/suggest-stream"` on the container div
- [x] 4.2 Add per-question loading indicators inside each `.suggestion-zone` so respondents
      see feedback before their question's suggestion arrives
- [x] 4.3 Update `suggestion_block.html` to include `hx-swap-oob="true"` and the correct
      `id` attribute for OOB placement; remove the afterSwap JS handler from `survey.html`
      that previously moved suggestion blocks from the container to their zones
- [x] 4.4 Revert the temporary `timeout=300.0` workaround in `m_ui/api_client.py` back to
      `60.0` (or remove the function entirely if step 3.5 is complete)

## 5. Tests

- [x] 5.1 Unit test `suggest_batch_stream` generator: verify it yields one dict per item and
      a graceful fallback on LLM failure
- [x] 5.2 Integration test `POST /suggest/stream`: verify SSE response headers, event format,
      and `event: done` terminator using `TestClient` with `stream=True`
- [x] 5.3 Update or remove tests covering the old `GET /session/{id}/suggest` endpoint in
      `tests/test_chat_api.py` or equivalent m-ui test file
