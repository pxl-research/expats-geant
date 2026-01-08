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
├── llm/
│   ├── __init__.py
│   ├── client.py             # Unified LLM client (OpenRouter, OpenAI-compat, local)
│   ├── models.py             # Supported LLM models and configurations
│   └── utils.py              # Prompt engineering, token counting
├── vectordb/
│   ├── __init__.py
│   ├── client.py             # ChromaDB wrapper
│   ├── session_store.py      # Per-session isolation
│   └── utils.py              # Chunking, embedding utilities
├── models/
│   ├── __init__.py
│   ├── survey.py             # Survey, Section, Question, AnswerOption
│   ├── response.py           # Response, Citation, SourceMetadata
│   ├── session.py            # Session, TTL, audit trail
│   └── qti.py                # QTI 3.0 schema mappings
├── auth/
│   ├── __init__.py
│   ├── jwt_handler.py        # JWT token creation, validation
│   ├── oauth.py              # OAuth 2.0 integration
│   └── permissions.py        # Role-based access control (RBAC)
├── utils/
│   ├── __init__.py
│   ├── logging.py            # Structured logging
│   ├── error_handling.py     # Custom exceptions, error formatting
│   ├── encryption.py         # Data encryption utilities
│   └── validators.py         # Input validation, sanitization
└── tests/
    ├── test_llm_client.py
    ├── test_vectordb_client.py
    ├── test_models.py
    ├── test_auth.py
    └── fixtures/
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

JWT and OAuth 2.0 support.

**Features:**

- Token generation and validation
- User identity assertion (sub, org, roles)
- Consent capture and consent verification
- Role-based access control (RBAC)

**Usage:**

```python
from m_shared.auth import create_jwt_token, verify_jwt_token

token = create_jwt_token(user_id="user-123", org="pxl", roles=["respondent"])
payload = verify_jwt_token(token)
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
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_LLM_MODEL=openai/gpt-4

# Local LLM (optional)
LOCAL_LLM_BASE_URL=http://localhost:11434

# Vector DB
CHROMADB_PATH=/tmp/chromadb
SESSION_TTL_HOURS=48

# Auth
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256

# Logging
LOG_LEVEL=INFO
```

## Development

### Running Tests

```bash
pytest m_shared/tests/ -v
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

- `pydantic` — Data validation & schema generation
- `chromadb` — Vector database
- `openai` — LLM client (OpenAI-compatible)
- `python-jose` — JWT handling
- `cryptography` — Encryption utilities

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
