# Shape: Administrator Questionnaire Design Co-Pilot

An AI-powered assistant that accelerates questionnaire and survey design with guardrails, consistency checks, intelligent tagging, and conversational authoring.

## What's Built

Shape is fully implemented. The module provides:

- **Suggestion engine** — proposes improved phrasings for survey questions, respecting style profiles
- **Validation engine** — Tier 1 deterministic rules (double-barreled questions, missing choices, etc.) + Tier 2 LLM checks
- **Tagging engine** — suggests normalised tags; accumulates a session vocabulary across questions
- **Conversation engine** — multi-turn dialogue that can create and update a draft survey in response to natural language instructions
- **Style engine** — extracts and summarises institutional style guide documents; applies style constraints to all AI outputs
- **Session manager** — file-based session storage (draft survey, tag vocabulary, conversation history, style profile)
- **REST API** — stateless transform endpoints (import/export/create) and context-aware tool endpoints (suggest/validate/tag), plus a full conversational session lifecycle

## Module Structure

```
shape_api/
├── __init__.py
├── api.py                # FastAPI app factory (create_app) — thin orchestrator
├── models.py             # Pydantic request/response models
├── session.py            # Session I/O helpers (load/save draft, vocabulary, style, conversation)
├── conversation.py       # Chat turn execution (LLM + draft update logic)
├── suggestion_engine.py  # Question phrasing suggestions
├── validation_engine.py  # Question and survey validation rules
├── tagging_engine.py     # Tag suggestion and vocabulary management
├── style.py              # Style document extraction and summarisation
└── routes/
    ├── __init__.py
    ├── auth.py           # /auth/token, /auth/login, /auth/callback
    ├── transforms.py     # /import, /export, /create
    ├── tools.py          # /suggest, /validate, /tag
    └── chat.py           # All /chat/... endpoints (sessions, messages, style, upload)
```

Routes access shared dependencies (session manager, LLM client) via `request.app.state`,
set by `create_app()` in `api.py`.

## Quick Start

### 1. Generate a token

```bash
TOKEN=$(curl -s -X POST "http://localhost:8001/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"dev_user","api_secret":"your-shared-api-secret"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

### 2. Get a question suggestion

```bash
curl -X POST http://localhost:8003/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": {"id": "q1", "type": "open_ended", "text": "How do you feel about workload?"},
    "n_suggestions": 2
  }'
```

### 3. Start a conversational design session

```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8003/chat/sessions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Send a design instruction
curl -X POST "http://localhost:8003/chat/$SESSION" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a short survey about remote work with 3 questions"}'

# Retrieve the draft
curl "http://localhost:8003/chat/$SESSION/survey" \
  -H "Authorization: Bearer $TOKEN"
```

## API Summary

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/import` | POST | Yes | Parse platform survey → internal JSON |
| `/export` | POST | Yes | Internal JSON → platform format |
| `/create` | POST | Yes | Create on platform API or export to file |
| `/suggest` | POST | Yes | Suggest improved question phrasings |
| `/validate` | POST | Yes | Validate question or survey for issues |
| `/tag` | POST | Yes | Suggest and persist question tags |
| `/chat/sessions` | POST | Yes | Create conversational session |
| `/chat/sessions` | GET | Yes | List user's sessions |
| `/chat/{id}` | GET | Yes | Session metadata |
| `/chat/{id}` | POST | Yes | Send message, get AI response |
| `/chat/{id}/survey` | GET | Yes | Current draft survey |
| `/chat/{id}/messages` | GET | Yes | Conversation history |
| `/chat/{id}` | DELETE | Yes | Delete session |
| `/chat/{id}/reset` | POST | Yes | Clear draft + vocabulary |
| `/chat/{id}/style` | GET/PUT | Yes | Read/update style profile |
| `/chat/{id}/style/upload` | POST | Yes | Upload style guide document |
| `/chat/{id}/upload` | POST | Yes | Upload content document |

Full API reference: [docs/MCHAT_API.md](../docs/MCHAT_API.md)

## Testing

```bash
# Run all Shape tests (from repo root)
pytest tests/test_chat*.py -v

# Run with coverage
pytest tests/test_chat*.py -v --cov=shape_api --cov-report=term-missing
```

There are 9 Shape test files covering ~234 tests:

| File | Coverage |
|---|---|
| `test_chat_api.py` | Stateless endpoints (import/export/create/suggest/validate/tag) |
| `test_chat_conversational_api.py` | Chat session lifecycle, turns, survey retrieval |
| `test_chat_adapters.py` | Adapter create_survey for all four platforms |
| `test_chat_suggestion.py` | Suggestion engine unit tests |
| `test_chat_validation.py` | Validation engine unit tests |
| `test_chat_tagging.py` | Tagging engine unit tests |
| `test_chat_session.py` | Session I/O helpers |
| `test_chat_style.py` | Style extraction and summarisation |
| `test_chat_ui.py` | Shape UI integration |

Run the full suite for accurate coverage (single-file runs will fail `--cov-fail-under=80`):

```bash
pytest tests/ -v --tb=short
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `change-me-in-production` | JWT signing secret (shared with Cue) |
| `OPENROUTER_API_KEY` | — | LLM API key (required for suggest/tag/chat) |
| `LLM_MODEL` | `anthropic/claude-haiku-4.5` | LLM model identifier |
| `SESSION_TTL_HOURS` | `24` | Chat session lifetime in hours |
| `MAX_FILE_SIZE_MB` | `50` | Max file size for uploads |
| `API_SECRET` | — | Shared secret for `POST /auth/token` (omit to disable) |
| `CHAT_PORT` | `8003` | API server port |

## Links

- [Shape API Reference](../docs/MCHAT_API.md)
- [Data Model](../docs/DATA_MODEL.md)
- [Adapter Guide](../docs/ADAPTERS.md)
- [Testing Guide](../docs/TESTING.md)
- [M-Shared Utilities](../m_shared/README.md)
