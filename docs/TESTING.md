# Testing Guide

This document describes the conformance test suite for the Expats project (D2.1 deliverable).

## Running the Full Suite

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests with coverage
pytest tests/ -v --tb=short

# Run with HTML coverage report
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Open coverage report (macOS)
open htmlcov/index.html
```

Coverage threshold: `--cov-fail-under=80` (configured in `pyproject.toml` / `setup.cfg`).

**Note**: Running a single test file in isolation will fail the coverage threshold check. This is expected — the threshold is enforced against the full suite.

## Test Suite Map

### Cue (`cue_api/`)

| File | Description |
|---|---|
| `test_session_api.py` | Cue API endpoints (upload, batch suggest, session stats, delete) |
| `test_batch_suggest.py` | Batch suggestion endpoint with sections and flat item lists |
| `test_rag_pipeline.py` | RAG pipeline: document ingestion, chunking, retrieval |
| `test_rag_integration.py` | End-to-end RAG with ChromaDB (integration) |
| `test_rag_tools.py` | RAG utility functions |
| `test_document_ingestion.py` | Document parsing (PDF, DOCX, TXT, MD) |
| `test_chunking.py` | Text chunking strategies |
| `test_filtered_search.py` | Filtered vector search |
| `test_integration_ingestion.py` | Upload → ingest → search integration |
| `test_integration_batch.py` | Batch suggest integration |
| `test_audit.py` | Audit log creation and retrieval |
| `test_audit_integration.py` | Audit log API integration |
| `test_metadata.py` | Document metadata handling |
| `test_llm_client.py` | LLM client (OpenRouter/OpenAI) |
| `test_validation.py` | File upload validation |
| `test_validators.py` | Input validators |
| `test_upload_text.py` | Text snippet ingestion — ingest helper, API endpoint, and UI route |
| `test_live_api_import_api.py` | `POST /surveys/import-from-api` endpoint integration tests |
| `test_answer_report.py` | Per-session `answer_report.json` persistence and download endpoint |
| `test_autofill_suggest_stream.py` | `POST /suggest/stream` SSE endpoint: event format, done sentinel, mid-stream error handling |

### Shape (`shape_api/`)

| File | Description |
|---|---|
| `test_chat_api.py` | Stateless endpoints: import, export, create, suggest, validate, tag |
| `test_chat_conversational_api.py` | Session lifecycle: create, chat turns, survey retrieval, delete, reset |
| `test_chat_adapters.py` | `create_survey()` for LimeSurvey, Qualtrics, SurveyMonkey, QTI |
| `test_chat_suggestion.py` | Suggestion engine unit tests |
| `test_chat_validation.py` | Validation engine: deterministic rules and LLM checks |
| `test_chat_tagging.py` | Tagging engine and vocabulary persistence |
| `test_chat_session.py` | Session I/O helpers (load/save draft, vocabulary, style, conversation) |
| `test_chat_style.py` | Style document extraction and summarisation |
| `test_chat_ui.py` | Shape UI integration |

### Shared (`m_shared/`)

| File | Description |
|---|---|
| `test_adapters.py` | Platform adapter import/export (LimeSurvey, Qualtrics, SurveyMonkey, QTI) |
| `test_models.py` | Shared Pydantic models (Survey, Question, Choice) |
| `test_session_manager.py` | SessionManager: create, get, list, delete, TTL expiry |
| `test_session_isolation.py` | Cross-session data isolation |
| `test_auth.py` | JWT middleware: valid tokens, expired tokens, missing headers |
| `test_auth_token.py` | `POST /auth/token` endpoint: JWT issuance, secret validation, rate limiting |
| `test_oauth.py` | OIDC login and callback flows |
| `test_dev_token.py` | Development token issuance and validation |
| `test_rate_limit.py` | Rate limiting middleware |
| `test_startup_checks.py` | Startup configuration validation |
| `test_tool_calling.py` | LLM tool/function calling |
| `test_live_api_import_adapters.py` | `LimeSurveyAdapter.fetch_survey` and `QualtricsAdapter.fetch_survey` unit tests |

### Cue UI (`cue_ui/`)

| File | Description |
|---|---|
| `test_ui_routes.py` | UI route rendering including SSE suggest-stream proxy |
| `test_ui_modes.py` | Upload UI modes |
| `test_ui_api_client.py` | Cue UI → Cue API client |
| `test_ui_documents.py` | Document upload UI flow |

## Running Against a Deployed Instance

To smoke-test a running deployment:

### 1. Configure environment

```bash
export JWT_SECRET=your-deployed-secret
export BASE_URL=http://localhost:8001   # Cue
export CHAT_URL=http://localhost:8003   # Shape
```

### 2. Generate a token

```bash
TOKEN=$(curl -s -X POST "$BASE_URL/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "smoke_test", "api_secret": "$API_SECRET"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

> **Multi-tenant deployments:** Use the tenant's API secret instead of the global `API_SECRET` to obtain a tenant-scoped token. The resulting JWT `org` claim will route LLM calls through the tenant's credentials.

### 3. E2E spot-check scripts

Four automated scripts cover the full deployed stack:

```bash
# Cue: upload → suggest → audit → cleanup (52 checks)
python tests/scripts/e2e_api_spot_check.py --base-url $BASE_URL

# Cue: /suggest/stream SSE endpoint (27 checks)
python tests/scripts/e2e_stream_spot_check.py --base-url $BASE_URL

# Cue: audit trail accuracy, timestamps, GDPR deletion (80 checks)
python tests/scripts/e2e_audit_spot_check.py --base-url $BASE_URL

# Shape: import/export, validate, suggest, tag (30 checks)
python tests/scripts/e2e_chat_spot_check.py --base-url $CHAT_URL

# Shape: conversational session lifecycle (33 checks)
python tests/scripts/e2e_chat_conversational_spot_check.py --base-url $CHAT_URL
```

### 4. Curl smoke tests

```bash
# Cue health
curl $BASE_URL/health
# {"status":"healthy"}

# Shape health
curl $CHAT_URL/health
# {"status":"healthy"}

# Authenticated Shape suggest
curl -X POST $CHAT_URL/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": {"id":"q1","type":"open_ended","text":"What is your role?"}, "n_suggestions":1}'
```

## Skipping LLM-Dependent Tests

Some tests require a live LLM API key (`OPENROUTER_API_KEY` or `OPENAI_API_KEY`). Tests that call the LLM directly are marked or skip automatically when no key is present.

To run only deterministic (non-LLM) tests:

```bash
# Skip any test that requires live LLM calls by running without API key
unset OPENROUTER_API_KEY
pytest tests/ -v --tb=short
```

Tests that exercise LLM-backed endpoints in isolation typically mock the LLM client and do not require a real key.

## Coverage Report

```bash
# Terminal summary
pytest tests/ --cov=. --cov-report=term-missing

# HTML report (detailed, per-file)
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest tests/ --cov=. --cov-report=xml
```

The coverage threshold is 80% across the full codebase. Key modules with high coverage: `m_shared/`, `cue_api/`, `shape_api/`.
