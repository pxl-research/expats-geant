# M-Shared: Common Utilities & Infrastructure

Shared utilities, data models, and client abstractions for both M-Chat and M-Autofill modules.

## Overview

M-Shared provides the foundational infrastructure and utilities that both M-Chat and M-Autofill depend on:

- **LLM client abstraction** — Unified interface to OpenRouter, OpenAI-compatible APIs, and local LLMs
- **Vector DB client** — ChromaDB wrapper with tenant/session isolation
- **Data models** — Survey, Question, Response, Citation, Session, and other core entities
- **Utilities** — Document chunking, embedding, metadata management, error handling
- **Auth & security** — JWT token handling, CORS, secrets management

## Module Structure

```
m_shared/
├── __init__.py
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
│   └── audit.py             # Audit trail logging
└── vectordb/
    ├── __init__.py
    ├── client.py             # ChromaDB wrapper with session isolation
    └── utils.py             # Chunking & embedding utilities
```

> Files listed in an earlier version of this README (`vectordb/session_store.py`, `utils/logging.py`, `utils/error_handling.py`, `utils/encryption.py`, `utils/validators.py`, `models/qti.py`, `auth/permissions.py`, `llm/models.py`, `llm/utils.py`) are **planned for future phases** and do not yet exist.

## Key Components

### LLM Client (`llm/client.py`)

Unified abstraction over multiple LLM providers.

**Features:**

- EU-hosted & open models: Mistral, Meta Llama, and other EU-based providers (preferred to avoid cross-border data transfer)
- OpenRouter access: Cost-optimized multi-model gateway with configurable provider filtering
- OpenAI-compatible APIs: Fallback to OpenAI, Anthropic, or other endpoints if needed
- Local LLM support: Ollama, LM Studio, or other self-hosted models for fully on-premise deployments
- Automatic retry, rate-limiting, token counting

**Usage:**

```python
from m_shared.llm import get_llm_client

client = get_llm_client()  # Uses env config
response = await client.generate(
    prompt="Rewrite this question for clarity...",
    model="openai/gpt-4",
    temperature=0.7
)
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
from m_shared.vectordb import get_vectordb_client

client = get_vectordb_client(session_id="user-123")
client.add_documents(chunks=[...], metadata=[...])
results = await client.search(query="...", top_k=5)
client.cleanup()  # On session end
```

### Data Models (`models/`)

Pydantic models for surveys, responses, sessions, and QTI mapping.

**Core models:**

- `Survey` — Questionnaire with sections and questions
- `Question` — Individual question with answer options
- `Response` — User submission with answer values
- `Citation` — Source reference with position/timestamp
- `Session` — User session with TTL and isolation scope
- `QTISurvey` — QTI 3.0-compatible schema

All models include validation and serialization to JSON/XML.

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
# Returns a platform JWT signed by JWT_SECRET — same format as /dev/token
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

Common utilities for logging, error handling, encryption, and validation.

**Features:**

- Structured logging with context (session_id, user_id, request_id)
- Custom exceptions with error codes and messages
- Data encryption (AES-256 where needed)
- Input sanitization and validation

## Configuration

Environment variables (see `.env.example`):

```bash
# LLM Configuration
OPENROUTER_API_KEY=sk_...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-haiku-4.5

# Vector DB
CHROMA_BASE_PATH=/app/data/chroma
SESSION_TTL_HOURS=24

# Auth
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256

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

### Adding LLM Provider Support

1. Extend `llm/models.py` with new provider configuration
2. Update `llm/client.py` routing logic
3. Add tests with mock provider responses
4. Document in README

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

M-Shared is imported by M-Chat and M-Autofill. Both modules depend on:

```python
from m_shared.llm import get_llm_client
from m_shared.vectordb import get_vectordb_client
from m_shared.models import Survey, Response, Citation, Session
from m_shared.auth import verify_jwt_token, create_jwt_token
```

## Roadmap

- ✅ Basic LLM client (OpenRouter, OpenAI-compat)
- ✅ ChromaDB wrapper with session isolation
- ✅ Core data models (Survey, Response, Citation, Session)
- 🚧 Local LLM integration (Ollama, LM Studio)
- 🚧 PostgreSQL models (future)
- 📅 Advanced encryption & key management (future)
- 📅 Distributed session store (Redis, future)

## References

- [Project Context](../openspec/project.md)
- [M-Autofill Module](../m_autofill/README.md)
- [M-Chat Module](../m_chat/README.md)
