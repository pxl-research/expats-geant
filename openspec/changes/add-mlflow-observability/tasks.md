## 1. Infrastructure

- [ ] 1.1 Add MLFlow service to `docker-compose.yml` (image: `ghcr.io/mlflow/mlflow`, SQLite backend, port 5000, `--app-name basic-auth`)
- [ ] 1.2 Add `MLFLOW_TRACKING_URI`, `MLFLOW_TRACE_CONTENT`, `MLFLOW_EVAL_ENABLED`, `MLFLOW_ADMIN_USERNAME`, and `MLFLOW_ADMIN_PASSWORD` to `.env.example` with safe defaults (URI unset, content off, eval off)
- [ ] 1.3 Document MLFlow service in deployment README (how to enable/disable, how to set credentials)

## 2. Tracing Adapter (m_shared)

- [ ] 2.1 Create `m_shared/observability/tracer.py` — thin wrapper around `mlflow` that checks `MLFLOW_TRACKING_URI` at init; exposes `trace_llm_call()` and `trace_rag_pipeline()` helpers that are no-ops when MLFlow is not configured
- [ ] 2.2 Implement session ID pseudonymisation (one-way hash) in the tracer
- [ ] 2.3 Implement content-filtering logic: exclude prompt/response/chunk text unless `MLFLOW_TRACE_CONTENT=true`
- [ ] 2.4 Write unit tests: verify no-op behaviour when `MLFLOW_TRACKING_URI` is unset; verify metadata logged and content excluded with defaults

## 3. Instrument m_autofill RAG Pipeline

- [ ] 3.1 Wrap embedding calls in `m_autofill/` with `tracer.trace_rag_pipeline()` (embedding model, latency)
- [ ] 3.2 Wrap retrieval calls (chunk count, retrieval latency)
- [ ] 3.3 Wrap LLM generation call with `tracer.trace_llm_call()`
- [ ] 3.4 Write integration test: verify trace entries are created with expected metadata fields

## 4. Instrument m_chat Engines

- [ ] 4.1 Wrap LLM calls in `m_chat/` engines with `tracer.trace_llm_call()`
- [ ] 4.2 Write integration test: verify trace entries created; verify no content logged by default

## 5. Trace Data Retention

- [ ] 5.1 Extend session cleanup job to delete MLFlow trace data for expired sessions (aligned with session TTL)
- [ ] 5.2 Write test: verify trace data is removed when session cleanup runs

## 6. LLM Evaluation Setup

- [ ] 6.1 Add `litellm` to `requirements-eval.txt` (version-pinned); keep separate from main requirements to avoid bloating the base image
- [ ] 6.2 Create `scripts/run_evaluation.py` — evaluation script that loads trace data from MLFlow and runs faithfulness, answer relevance, and context relevance metrics; invoked automatically at session end when `MLFLOW_EVAL_ENABLED=true`
- [ ] 6.3 Configure LiteLLM OpenRouter judge (`openrouter/<model>` format, reads `OPENROUTER_API_KEY`)
- [ ] 6.4 Hook evaluation trigger into session cleanup/end path: call `run_evaluation.py` for the session if `MLFLOW_EVAL_ENABLED=true` and `MLFLOW_TRACE_CONTENT=true`
- [ ] 6.5 Document the three env flags and their interaction (`MLFLOW_EVAL_ENABLED` requires `MLFLOW_TRACE_CONTENT` to produce meaningful results)

## 7. Validation

- [ ] 7.1 Run `openspec validate add-mlflow-observability --strict` and resolve any issues
- [ ] 7.2 Smoke test: start docker-compose with MLFlow enabled, run a suggestion request, verify trace appears in MLFlow UI
- [ ] 7.3 Smoke test: start docker-compose without `MLFLOW_TRACKING_URI`, verify application runs normally with no errors
