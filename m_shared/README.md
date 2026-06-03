# M-Shared: Common Utilities & Infrastructure

Shared utilities, data models, and client abstractions for both Shape and Cue modules.

## Overview

M-Shared provides the foundational infrastructure and utilities that both Shape and Cue depend on:

- **LLM client abstraction** — Unified interface to OpenRouter, OpenAI-compatible APIs, and local LLMs
- **Vector DB client** — ChromaDB wrapper with tenant/session isolation
- **Data models** — Survey, Question, Response, Citation, Session, and other core entities
- **Survey adapters** — Import/export/submit adapters for LimeSurvey, Qualtrics, SurveyMonkey, and QTI 3.0; extensible via `SurveyAdapter` base class (see [docs/ADAPTERS.md](../docs/ADAPTERS.md))
- **Utilities** — Document chunking, embedding, metadata management, error handling
- **Auth & security** — JWT token handling, CORS, secrets management

## Module Structure

```
m_shared/
├── __init__.py
├── adapters/
│   ├── __init__.py
│   ├── base.py               # Abstract SurveyAdapter base class
│   ├── limesurvey.py         # LimeSurvey LSS XML adapter
│   ├── qti.py                # QTI 3.0 XML adapter
│   ├── qualtrics.py          # Qualtrics QSF JSON adapter
│   ├── registry.py           # Adapter factory (get_adapter)
│   └── surveymonkey.py       # SurveyMonkey API v3 JSON adapter
├── auth/
│   ├── __init__.py
│   ├── jwt_handler.py        # JWT token creation & validation
│   ├── middleware.py         # FastAPI auth middleware
│   ├── oauth.py              # OIDC discovery, code exchange, token validation
│   └── validators.py        # Token claim validators
├── llm/
│   ├── __init__.py
│   ├── client.py             # Unified LLM client (OpenRouter, OpenAI-compat)
│   └── tool_calling.py      # LLM tool/function calling helpers
├── models/
│   ├── __init__.py
│   ├── answer_option.py
│   ├── citation.py
│   ├── question.py
│   ├── response.py
│   ├── section.py
│   ├── session.py
│   └── survey.py
├── session/
│   ├── __init__.py
│   └── manager.py            # Session lifecycle, TTL, cleanup
├── utils/
│   ├── __init__.py
│   ├── audit.py             # Audit trail logging
│   ├── file_validation.py   # File upload validation (type, size, extension)
│   ├── llm_parsing.py       # LLM output parsing (strip code fences)
│   └── url_validation.py    # URL and datacenter ID validation (SSRF prevention)
└── vectordb/
    ├── __init__.py
    ├── client.py             # ChromaDB wrapper with session isolation
    └── utils.py             # Chunking & embedding utilities
```

## Key Components

### LLM Client (`llm/client.py`)

Unified abstraction over multiple LLM providers.

**Features:**

- EU-hosted & open models: Mistral, Meta Llama, and other EU-based providers (preferred to avoid cross-border data transfer)
- OpenRouter access: Cost-optimized multi-model gateway with configurable provider filtering
- OpenAI-compatible APIs: Fallback to OpenAI, Anthropic, or other endpoints if needed
- Local LLM support: Ollama, LM Studio, or other self-hosted models for fully on-premise deployments
- Automatic retry, rate-limiting, token counting
- Extended thinking budget: optional `thinking_budget` parameter (or `THINKING_BUDGET_TOKENS` env var) for Claude 3.5+/4.x reasoning models

**Usage:**

```python
from m_shared.llm import LLMClient

client = LLMClient()  # Uses env config (OPENROUTER_API_KEY, DEFAULT_LLM_MODEL)
response = client.create_completion(
    messages=[{"role": "user", "content": "Rewrite this question for clarity..."}],
)

# With extended thinking (Claude 3.5+/4.x only):
client = LLMClient(thinking_budget=8000)  # or set THINKING_BUDGET_TOKENS=8000 in env
response = client.create_completion(messages=[...])
```

### Vector DB Client (`vectordb/client.py`)

ChromaDB wrapper with session-based isolation.

**Features:**

- Per-session ephemeral databases (cleanup on session end)
- Document chunking with metadata (source, position, timestamp)
- Semantic search with metadata filtering
- TTL-based automatic cleanup

**Usage:**

```python
from m_shared.vectordb import ChromaDocumentStore

client = ChromaDocumentStore(session_id="user-123")
client.add_documents(chunks=[...], metadata=[...])
results = client.search(query="...", top_k=5)
client.cleanup()  # On session end
```

### Data Models (`models/`)

Pydantic models for surveys, responses, sessions, and QTI mapping.

**Core models:**

- `Survey` — Questionnaire with sections and questions
- `Section` — Group of questions within a survey
- `Question` — Individual question with answer options
- `AnswerOption` — Choice for single/multiple-choice questions
- `Response` — User submission with answer values
- `Citation` — Source reference with position/timestamp
- `Session` — User session with TTL and isolation scope

All models include Pydantic validation and JSON serialization.

### Session Management (`session/`)

Per-session isolation for vector stores and document storage with TTL-based
cleanup.

**Layout** — sessions are grouped per user under a short SHA-256 of the
user_id; deletion = folder removal:

```
sessions/
└── <sha256(user_id)[:16]>/
    └── <session_id>/
        ├── chroma_<hex>/    # Isolated ChromaDB instance
        ├── uploads/         # Uploaded documents (optional)
        └── metadata.json    # Session metadata (user_id, expires_at, ...)
```

**Session IDs** are server-generated (UUID4 hex truncated to 12 characters by
default). Callers may pass `explicit_session_id` to `create_session` for
stable URLs (e.g. resumable autofill links), in which case the same ID
always resolves to the same session for the same user. The legacy
`jwt_token` argument on `create_session` is retained for backward
compatibility and is no longer used to derive the ID.

**Composition, not inheritance** — `SessionManager` uses
`ChromaDocumentStore` rather than extending it, keeping session lifecycle
and vector operations cleanly separated and reusable across Cue and Shape.

**TTL and cleanup defaults** are documented in
[`docs/OPERATOR_RUNBOOK.md` §1.3](../docs/OPERATOR_RUNBOOK.md#13-data-retention).

```python
from m_shared.session import SessionManager

manager = SessionManager(base_path="./sessions")
session = manager.create_session(user_id="user_123")
store = manager.get_vector_store(session.session_id)
```

### Authentication (`auth/`)

JWT and OIDC support.

**Features:**

- Token generation and validation (`jwt_handler.py`)
- OIDC login flow: discovery, authorization URL, code exchange, ID token validation (`oauth.py`)
- FastAPI middleware with public-route bypass (`middleware.py`)
- Input sanitization and claim validation (`validators.py`)

**`oauth.py` public API:**

```python
from m_shared.auth.oauth import get_authorization_url, exchange_code

# 1. Build the OIDC redirect URL (call from GET /auth/login)
auth_url, state = await get_authorization_url()
# Redirect user to auth_url; store state implicitly (module-level, 10-min TTL)

# 2. Handle callback (call from GET /auth/callback)
platform_token = await exchange_code(code=code, state=state)
# Returns a platform JWT signed by JWT_SECRET — same format as POST /auth/token
```

Reads env vars: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`.
Falls back gracefully when env vars are absent (raises `OIDCConfigurationError`).

**`jwt_handler.py` usage:**

```python
from m_shared.auth import create_token, validate_token

token = create_token(user_id="user-123", session_id="sess-456", org="pxl", roles=["respondent"])
payload = validate_token(token)
```

### Utilities (`utils/`)

**`audit.py`** — Session-level audit trail for transparency and GDPR compliance.
Records document uploads, suggestion generation (with sources), user edits, and session lifecycle events. Audit reports let users verify which documents informed their answers.

**`file_validation.py`** — Shared file upload validation (extension allowlist, size limits, readability checks). Used by both Cue and Shape upload endpoints. `cue_api/validation.py` re-exports from here for backwards compatibility.

**`url_validation.py`** — SSRF prevention: validates external API URLs (HTTPS-only, blocks loopback/private IPs) and Qualtrics datacenter IDs. Used by both APIs for live platform imports.

**`llm_parsing.py`** — Strips markdown code fences from LLM output before JSON parsing. Used across suggestion, validation, and RAG pipeline modules.

## Configuration

Environment variables (see `.env.example`):

```bash
# LLM Configuration
OPENROUTER_API_KEY=sk_...
LLM_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_LLM_MODEL=anthropic/claude-haiku-4.5  # shared fallback; docker-compose maps CUE_LLM_MODEL / SHAPE_LLM_MODEL to LLM_MODEL per container

# Vector DB
CHROMA_BASE_PATH=/app/data/chroma
SESSION_TTL_HOURS=24

# Auth
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
API_SECRET=your-shared-api-secret   # Required for POST /auth/token

# LLM extended thinking (optional, Claude 3.5+/4.x only)
THINKING_BUDGET_TOKENS=8000

# Logging
LOG_LEVEL=INFO
```

## Development

### Running Tests

```bash
# Tests live in the repo root tests/ folder
pytest tests/ -v
```

### Adding a New Model

1. Create model class in `models/` with Pydantic validation
2. Add JSON schema generation
3. Write unit tests in `tests/`
4. Document in this README

Example:

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Human-readable name")

    class Config:
        json_schema_extra = {"example": {"id": "ex-1", "name": "Example"}}
```

## Privacy & Security

- **Data minimization**: No logging of sensitive user data (documents, responses)
- **Configurable redaction**: LLM processing instructions can include redaction rules to mask or exclude sensitive information before passing data to external AI services
- **Encryption**: Sensitive data encrypted at rest where applicable
- **Secrets management**: All API keys and secrets via environment variables
- **Audit logging**: Structured logs with session context for traceability
- **Input sanitization**: All user inputs validated and sanitized

## Dependencies

See root `requirements.txt`. Key libraries:

- `pydantic` — Data validation & schema generation (transitive dependency via FastAPI)
- `chromadb` — Vector database
- `openai` — LLM client (OpenAI-compatible)
- `PyJWT` — JWT handling
- `fastapi` — Web framework

## Integration

M-Shared is imported by Shape and Cue. Both modules depend on:

```python
from m_shared.llm import get_llm_client
from m_shared.vectordb import get_vectordb_client
from m_shared.models import Survey, Response, Citation, Session
from m_shared.auth import create_token, validate_token
```

## References

- [Project Context](../openspec/project.md)
- [Cue Module](../cue_api/README.md)
- [Shape Module](../shape_api/README.md)
