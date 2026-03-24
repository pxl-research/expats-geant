# Design: Stream batch suggestions via SSE

## Context

The existing `POST /suggest/batch` endpoint processes all questions sequentially before
returning a single JSON response. LLM latency is ~3–10s per question; a 15-question
survey takes 45–150s total, which exceeds the m-ui HTTP timeout and leaves the browser
with no feedback until all questions are done — or until it times out.

FastAPI supports `StreamingResponse` with Server-Sent Events. HTMX's SSE extension
(`hx-ext="sse"`) can consume an SSE stream and progressively swap HTML fragments into
the page. These two primitives compose cleanly with the existing sequential processing
loop.

## Goals / Non-Goals

- **Goals:**
  - Suggestions appear in the browser as each LLM call completes (progressive delivery)
  - Eliminate the connection timeout problem for large surveys
  - Unblock the m-autofill event loop during LLM calls
  - Reuse the existing `suggestion_block.html` partial and question zone structure
  - Retain `POST /suggest/batch` unchanged for non-UI API consumers

- **Non-Goals:**
  - Parallel LLM calls (sequential order preserved; parallelism is post-PoC scope)
  - Persistent job queue / polling (unnecessary complexity for PoC scale)
  - Changes to m-autofill's retrieval or generation logic

## Decisions

### SSE over WebSocket
SSE is unidirectional (server → client), which is all we need here. It works over plain
HTTP/1.1, requires no upgrade handshake, and is natively supported by HTMX's SSE
extension. WebSocket adds bidirectional complexity with no benefit for this use case.

### m-ui proxies the stream (does not expose m-autofill SSE directly to the browser)
The browser holds only a cookie (HttpOnly). The auth Bearer token must be injected
server-side by m-ui when forwarding to m-autofill. This preserves the existing auth
architecture — m-autofill is not directly browser-facing.

The m-ui proxy opens an `httpx` streaming GET to m-autofill, reads events, renders each
as HTML using Jinja2, and re-emits as an SSE event using `hx-swap-oob`.

### hx-swap-oob for per-question placement
The existing `survey.html` already has `<div id="sug-{question.id}">` zones for each
question. By adding `hx-swap-oob="true"` and `id="sug-{item_id}"` to each streamed
suggestion block, HTMX places each fragment into its correct zone automatically without
JavaScript. This removes the afterSwap handler currently used for this purpose.

### asyncio.run_in_executor for LLM calls
`LLMClient.create_completion` is a synchronous blocking call (OpenAI SDK). Calling it
directly inside an `async def` FastAPI endpoint or an async generator blocks the event
loop, preventing concurrent requests. Wrapping it in `asyncio.run_in_executor(None, ...)`
offloads it to the default thread pool, restoring async behaviour.

### Request format: POST (not GET) for /suggest/stream
Mirrors `POST /suggest/batch` — accepts the same `BatchSuggestRequest` body.
SSE endpoints are typically GET, but GET cannot carry a body. Using POST is correct here;
HTMX SSE extension supports POST via `sse-connect` with a small JS shim, or we keep the
connection establishment as GET on the m-ui side (the proxy sends POST to m-autofill
internally).

Chosen approach: **m-ui exposes GET /session/{id}/suggest-stream** (no body needed —
session and survey ID come from the path and JWT). m-ui internally sends
`POST /suggest/stream` to m-autofill with the full `BatchSuggestRequest` body.

### SSE event format
Each event emitted by m-autofill:
```
event: suggestion
data: {"item_id": "...", "type": "...", "suggestion": "...", "selected_id": null,
       "selected_ids": null, "reasoning": "...", "citations": [...]}

```
A final `event: done` with empty data signals stream completion.

m-ui re-emits each as:
```
event: suggestion
data: <div id="sug-{item_id}" hx-swap-oob="true">...rendered HTML...</div>

```

## Risks / Trade-offs

- **HTTP/1.1 proxy buffering**: Some reverse proxies buffer SSE streams, breaking
  progressive delivery. Mitigation: set `X-Accel-Buffering: no` and
  `Cache-Control: no-cache` headers on SSE responses. Acceptable risk for PoC (deployed
  without a buffering proxy in dev).
- **Partial failure visibility**: If the LLM fails mid-stream after some suggestions have
  been displayed, earlier suggestions remain visible. A final error event should be
  emitted. This is strictly better than the current all-or-nothing batch failure.
- **Thread pool exhaustion**: `run_in_executor` uses the default thread pool. With many
  concurrent sessions, this could saturate. Acceptable at PoC scale.

## Migration Plan

1. Deploy new `/suggest/stream` endpoint alongside existing `/suggest/batch` (no removal).
2. Update m-ui to use the stream endpoint.
3. Remove the temporary `timeout=300.0` workaround from `m_ui/api_client.py`.
4. `POST /suggest/batch` remains available; no consumer migration required.

## Open Questions

- Should the stream include a progress event (e.g. `event: progress\ndata: {"done": 3, "total": 10}`)
  to drive a progress indicator? Nice-to-have; can be added without changing the protocol.
