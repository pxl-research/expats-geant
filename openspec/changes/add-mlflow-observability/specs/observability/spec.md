## ADDED Requirements

### Requirement: MLFlow Tracking Service

The system SHALL support an optional MLFlow tracking server deployed as a standalone
Docker container with a SQLite backend.

#### Scenario: Service starts with SQLite backend and basic auth

- **WHEN** the MLFlow container starts
- **THEN** it initialises a SQLite tracking store, enables basic auth, and exposes the UI on port 5000

#### Scenario: System runs without MLFlow

- **WHEN** `MLFLOW_TRACKING_URI` is not set in the environment
- **THEN** all tracing calls are no-ops and the application behaves identically to a
  non-instrumented deployment

#### Scenario: System connects to MLFlow

- **WHEN** `MLFLOW_TRACKING_URI` is set and the tracking server is reachable
- **THEN** the application registers itself and begins logging traces

---

### Requirement: LLM Call Tracing

The system SHALL trace each LLM call with operational metadata when observability is
enabled, without logging prompt or response content by default.

#### Scenario: Successful LLM call traced

- **WHEN** a successful LLM call completes and tracing is enabled
- **THEN** a trace entry is created containing:
  - Model name
  - Latency (ms)
  - Prompt token count
  - Completion token count
  - HTTP status code

#### Scenario: Failed LLM call traced

- **WHEN** an LLM call fails (rate limit, timeout, error) and tracing is enabled
- **THEN** a trace entry is created containing the error type and latency
- **AND** no prompt content is logged

#### Scenario: Content logging is opt-in

- **WHEN** `MLFLOW_TRACE_CONTENT` is not set or is set to `false`
- **THEN** prompt text and response text are excluded from all trace entries

#### Scenario: Content logging when explicitly enabled

- **WHEN** `MLFLOW_TRACE_CONTENT=true` is set
- **THEN** prompt text and response text are included in trace entries

---

### Requirement: RAG Pipeline Tracing

The system SHALL trace each RAG pipeline execution with retrieval and generation metadata
when observability is enabled.

#### Scenario: RAG pipeline execution traced

- **WHEN** a suggestion is generated and tracing is enabled
- **THEN** a trace entry is created containing:
  - Embedding model name
  - Embedding latency (ms)
  - Number of chunks retrieved
  - Retrieval latency (ms)
  - LLM generation latency (ms)
  - Session ID (pseudonymous — hashed)

#### Scenario: Retrieved content excluded by default

- **WHEN** `MLFLOW_TRACE_CONTENT` is not set or is `false`
- **THEN** retrieved document chunk text is excluded from trace entries

---

### Requirement: Privacy-Safe Trace Configuration

The system SHALL ensure trace data is GDPR-compliant by default, with content logging
available only through explicit opt-in configuration.

#### Scenario: Default configuration logs no personal data

- **WHEN** tracing is enabled with default settings
- **THEN** no prompt text, document content, LLM responses, or user-identifiable data
  appears in any trace entry

#### Scenario: Session IDs are pseudonymous

- **WHEN** a session ID is included in a trace entry
- **THEN** it is a one-way hash of the original session ID, not the raw identifier

#### Scenario: Trace data TTL aligned with session TTL

- **WHEN** a session's TTL expires and session data is cleaned up
- **THEN** the corresponding MLFlow trace data is also scheduled for deletion
- **AND** deletion occurs within one TTL cycle of session expiry

---

### Requirement: LLM Evaluation

The system SHALL support on-demand LLM-based evaluation runs against logged traces,
using OpenRouter models as judge LLMs via LiteLLM.

#### Scenario: Evaluation runs automatically at session end

- **WHEN** a session ends and both `MLFLOW_EVAL_ENABLED=true` and `MLFLOW_TRACE_CONTENT=true` are set
- **THEN** an evaluation run is triggered automatically for that session
- **AND** MLFlow Evaluate computes the configured metrics (faithfulness, answer
  relevance, context relevance) and stores results in the tracking server

#### Scenario: Evaluation is skipped when not enabled

- **WHEN** a session ends and `MLFLOW_EVAL_ENABLED` is not set or is `false`
- **THEN** no evaluation run is triggered and no judge LLM calls are made

#### Scenario: OpenRouter judge via LiteLLM

- **WHEN** an evaluation run is configured with an `openrouter/<model>` judge
- **THEN** LiteLLM routes judge LLM calls to OpenRouter using the configured API key

#### Scenario: Evaluation does not require live session data

- **WHEN** an evaluation run is triggered
- **THEN** it operates on previously logged trace metadata only
- **AND** does not require access to original documents or active sessions

---

### Requirement: Session Outcome Metrics

The system SHALL log session-level behavioural metrics to MLflow at session end, derived
from the audit log, to support pilot evaluation (GIP D4.1).

#### Scenario: Cue session outcome logged at session end

- **WHEN** a Cue session ends (explicit DELETE or TTL expiry) and tracing is enabled
- **THEN** a session outcome run is logged to MLflow containing:
  - Session duration in seconds (SESSION_END timestamp − SESSION_START timestamp)
  - Total suggestions generated (count of SUGGEST audit events)
  - Total suggestions edited (count of EDIT_SUGGESTION audit events)
  - Acceptance rate (suggestions neither edited nor rejected ÷ total suggestions)
  - Edit rate (edited suggestions ÷ total suggestions)
  - Session ID (pseudonymous — hashed, consistent with LLM trace entries)

#### Scenario: Shape session outcome logged at session end

- **WHEN** a Shape session ends and tracing is enabled
- **THEN** a session outcome run is logged to MLflow containing:
  - Session duration in seconds
  - Total suggestion requests made (count of /suggest calls)
  - Total validation runs (count of /validate calls)
  - Survey exported (boolean — true if /export or /create was called)
  - Session ID (pseudonymous — hashed)

#### Scenario: Session outcome logged without content

- **WHEN** `MLFLOW_TRACE_CONTENT` is false (default)
- **THEN** session outcome metrics contain only counts, durations, and rates
- **AND** no question text, suggestion text, or document content is included

#### Scenario: Tracing disabled — no session outcome logged

- **WHEN** `MLFLOW_TRACKING_URI` is not set
- **THEN** no session outcome metrics are computed or logged
- **AND** session end proceeds normally with no MLflow dependency
