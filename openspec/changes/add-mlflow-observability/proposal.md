# Change: Add MLFlow Observability

## Why

The pilot phase (Jan–May 2026) generates valuable operational data — LLM call patterns, RAG retrieval quality, latency, token costs — that is currently invisible. Adding MLFlow as an optional observability layer lets the team monitor and evaluate the system during the pilot without waiting until post-pilot to understand what is happening inside it.

## What Changes

- Add a new `observability` capability covering LLM tracing, RAG pipeline tracing, and LLM-based evaluation
- New optional Docker service: MLFlow tracking server (SQLite backend, separate container)
- Thin tracing adapter in `m_shared/` wraps LLM calls and RAG pipeline steps; all calls are no-ops when MLFlow is not configured
- Privacy-safe by default: operational metadata only (model, latency, token counts); prompt/response content excluded unless explicitly opted in
- LLM evaluation support via LiteLLM, enabling OpenRouter models as judge LLMs
- Session outcome metrics logged at session end (duration, suggestion count, edit/acceptance rates) derived from audit log — covers GIP D4.1 pilot KPIs
- Software runs identically with or without the MLFlow service running

## Impact

- Affected specs: new `observability` capability
- Affected code: `m_shared/llm/client.py`, `m_autofill/` pipeline, `m_chat/` engines, `docker-compose.yml`
- No breaking changes to existing APIs or data models
