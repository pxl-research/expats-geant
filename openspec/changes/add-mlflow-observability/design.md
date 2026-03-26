# Design: MLFlow Observability

## Context

The pilot runs Jan–May 2026 at PXL University College and partner institutions. The team needs
visibility into LLM behaviour (latency, cost, errors) and RAG quality (retrieval relevance,
answer faithfulness) to iterate quickly during the pilot. MLFlow is chosen for its modular
adoption path, minimal code-change philosophy, and built-in LLM evaluation support.

Privacy constraints are strict: user-uploaded documents and survey responses must not leak
into the observability layer.

## Goals / Non-Goals

- Goals:
  - Trace LLM calls (model, latency, token counts, errors) in `m_autofill/` and `m_chat/`
  - Trace RAG pipeline steps (retrieval latency, chunk count, embedding model)
  - Enable post-session LLM evaluation runs (faithfulness, relevance) via MLFlow Evaluate
  - Keep integration optional: system runs unmodified when MLFlow is not deployed
  - Stay GDPR-compliant: no personal data in traces by default

- Non-Goals:
  - MLFlow model registry or model serving
  - PostgreSQL backend (SQLite sufficient for PoC)
  - Real-time dashboards or alerting
  - Tracing in the survey UI or auth layer

## Decisions

- **Optional via environment variable**: Tracing adapter checks `MLFLOW_TRACKING_URI` at
  startup. If unset, all tracing calls are no-ops. No code changes required to disable.

- **SQLite backend**: Lightweight, no extra infrastructure. Acceptable for pilot scale.
  Migrate to PostgreSQL post-pilot if retention or multi-user access becomes a requirement.

- **Metadata-only logging by default**: Prompts, retrieved chunks, and LLM responses are
  NOT logged unless `MLFLOW_TRACE_CONTENT=true` is explicitly set. This satisfies GDPR
  data minimisation and the project's privacy-by-default principle.

- **Pseudonymous session IDs in traces**: Session identifiers logged to MLFlow are hashed
  (one-way), preventing correlation with user identity.

- **LiteLLM for evaluation judge**: MLFlow Evaluate does not natively support OpenRouter.
  LiteLLM provides a thin compatibility layer (`openrouter/<model>` format) that routes
  evaluation judge calls through OpenRouter. Adds one dependency; version-pinned in
  requirements files.

- **Separate Docker container**: MLFlow server runs as an independent service in
  `docker-compose.yml`. No coupling to the API containers; can be omitted from any
  deployment profile.

- **Trace data TTL**: MLFlow trace data is retained for the same TTL as session data
  (~24–48h configurable). A scheduled cleanup job purges stale experiments aligned
  with session cleanup.

## Alternatives Considered

- **LangFuse**: Good LLM observability tool but adds a managed-cloud dependency by default;
  self-hosting is possible but adds more infra than MLFlow. Rejected for simplicity.
- **Custom structured logging (JSONL)**: Zero dependencies, but no UI, no evaluation
  framework, no aggregation. Rejected in favour of MLFlow's built-in eval support.
- **Weights & Biases**: Cloud-first; data locality concerns for EU pilot. Rejected.

## Risks / Trade-offs

- **Privacy leak risk**: If `MLFLOW_TRACE_CONTENT=true` is set in a production environment,
  document content could appear in MLFlow traces. Mitigation: document the flag clearly;
  default off; CI lint check to warn if enabled in production compose files.
- **LiteLLM version drift**: LiteLLM and MLFlow release independently; pinning both
  is required. Mitigation: lock versions in `requirements-eval.txt`; test on update.
- **SQLite contention**: High-concurrency pilot writes could slow SQLite. Mitigation:
  async write queue; acceptable for PoC scale (expected <50 concurrent sessions).

## Decisions (resolved)

- **Evaluation trigger — opt-in automatic**: Evaluation runs trigger automatically at
  session end, but only when `MLFLOW_EVAL_ENABLED=true` is set. Default is off, keeping
  the base deployment cost-free. Operators enable it on specific pilot deployments where
  token cost is acceptable. Requires `MLFLOW_TRACE_CONTENT=true` to produce meaningful
  results (faithfulness/relevance metrics need actual prompt and response text).

- **MLFlow UI authentication — built-in basic auth**: MLFlow's native basic auth is
  enabled via `--app-name basic-auth`. Credentials are provided through environment
  variables in Docker Compose. Sufficient for pilot; no reverse proxy needed.
