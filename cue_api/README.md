# Cue: Evidence-Based Answer Suggestion Assistant

An AI-powered respondent assistant that retrieves relevant passages from user documents, proposes concise answers with full citations, and transparently explains how suggestions were derived.

## Overview

Cue is a RAG (Retrieval-Augmented Generation) module that helps respondents complete surveys and forms more accurately and efficiently. When a respondent needs to answer a question, they can upload supporting documents (PDFs, Word docs, spreadsheets, presentations, or images). Cue:

1. **Retrieves**: Finds the most relevant passages from uploaded documents using semantic search
2. **Generates**: Proposes a concise draft answer informed by those passages
3. **Citations**: Shows exactly where information came from—line numbers, timestamps, highlights
4. **Explains**: Provides reasoning for why those sources were chosen

## Key Features

🔍 **Semantic Search & RAG**

- ChromaDB vector database for intelligent document retrieval
- Chunk-based storage with metadata (source, position, timestamp) for precise citations
- Multi-format support: PDF, DOCX, TXT, MD, PPTX, XLSX, XLS, and images (JPG, JPEG, PNG, GIF, WEBP — converted to text via LLM description)

📝 **Citation & Transparency**

- Full citation system: know which exact passages informed each answer
- Highlights and line numbers/percentages for easy document navigation
- Audit trail: why specific sources were retrieved and used

👤 **Privacy-First Design**

- Session-based isolation: each respondent session is independent
- Ephemeral storage: documents and vectors deleted after TTL expires (24h default, configurable)
- No profiling, no cross-session tracking
- GDPR-compliant with user consent capture

## Module Structure

```
cue_api/
├── __init__.py
├── api.py                   # FastAPI app factory (create_app) — thin orchestrator
├── ingest.py                # Document upload and ingestion pipeline (incl. URL-extracted text)
├── models.py                # Pydantic request/response models
├── rag_pipeline.py          # RAG orchestration: retrieval, generation, citations
├── rag_tools.py             # RAG tool wrappers for LLM tool calling
├── validation.py            # Re-exports from m_shared.utils.file_validation
├── web_fetch.py             # HTTP fetch + content-type routing (Trafilatura / MarkItDown)
└── routes/
    ├── __init__.py
    ├── auth.py              # /auth/token, /auth/login, /auth/callback
    ├── session.py           # /session/stats, DELETE /session, /privacy,
                             #   PUT /session/web-consent
    ├── documents.py         # /upload, /upload-text
    ├── suggestions.py       # /suggest/batch, /suggest/stream
    ├── audit.py             # /audit-report (GET/DELETE), /answer-report/download
    ├── surveys.py           # /surveys/import, /surveys/import-from-api, /surveys/{id},
                             #   /adapters/{format}/capabilities, /sessions/{id}/submit
    └── web.py               # /web/preview, /web/ingest
```

Routes access shared dependencies (session manager, LLM client, audit logger, RAG pipeline)
via `request.app.state`, set by `create_app()` in `api.py`.

Tests live in the repo root `tests/` folder.

## RAG Pipeline Architecture

### Core Components

**1. Retrieval (`retrieve()`)**

- Semantic search using ChromaDB vector store
- Session-scoped: only searches documents within the user's session
- Returns top-k chunks (default: 5) with full metadata
- Metadata includes: source filename, chunk index, position/percentage, timestamp

**2. Answer Generation (`_generate_answer_with_reasoning()`)**

- LLM-based generation from retrieved passages
- Returns structured `{answer, reasoning, selected}` JSON (tightened
  schema for choice-type questions)
- Temperature control (0.3–0.5 for slightly deterministic output)
- Max token limit: 500 tokens (configurable)
- Graceful error handling for API failures, rate limits, timeouts

**3. Citation Formatting (`format_citations()`)**

- Extracts source metadata from retrieved chunks
- Creates structured `Citation` objects with:
  - Source document name
  - Position in document (character offsets, percentage)
  - Upload timestamp
  - Text excerpts (50–200 chars) for verification
- Handles missing metadata gracefully

**4. Orchestration (`suggest_batch()` / `suggest_batch_stream()`)**

- End-to-end batch pipeline: rewrite-query → retrieve → generate → format
  citations → audit-log
- Sync (`suggest_batch`) and async-streaming (`suggest_batch_stream`)
  entry points, both driven by `_process_item` per question
- Accepts either grouped `sections` or a flat `items` list (see
  `BatchSuggestRequest`)
- Returns a list of `ItemSuggestion` dicts with `selected_id` /
  `selected_ids` populated for choice questions
- Handles edge cases: no documents, no chunk matches, LLM failure

### Design Decisions

**Temperature: 0.4** (default)

- Balances consistency with slight creativity
- Slightly deterministic output for reproducibility
- Can be overridden per request

**Top-K Retrieval: 5** (default)

- Provides enough context without overwhelming the LLM
- ChromaDB returns results sorted by semantic similarity
- No re-ranking in MVP; direct similarity-based ordering

**Session Isolation**

- Each session has its own ChromaDB instance (folder-based)
- Session manager handles creation, TTL, and cleanup
- Sessions tied to JWT tokens for security

**Citation Strategy**

- Citations linked to retrieved chunks (1:1 mapping)
- Text excerpts break at sentence/word boundaries when possible
- Position percentage calculated from chunk_index / total_chunks if not in metadata

### Testing

**Unit Tests** (`tests/test_rag_pipeline.py`)

- 31 tests covering all functions and edge cases
- Mocked dependencies (SessionManager, LLMClient, ChromaDB)
- Tests for: retrieval, generation, citations, orchestration, error handling

**Integration Tests** (`tests/test_rag_integration.py`)

- 8 end-to-end tests with real document ingestion
- Session isolation validation
- Multi-document scenarios
- Requires `OPENROUTER_API_KEY` environment variable

Run tests:

```bash
# Unit tests (no API key required) — run from repo root
pytest tests/test_rag_pipeline.py -v

# Integration tests (requires API key)
OPENROUTER_API_KEY=your_key pytest tests/test_rag_integration.py -v
```

## API Endpoints

Session identity is carried in the JWT token (Authorization header). All endpoints below are session-scoped automatically.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/upload` | Upload a document into the session |
| `POST` | `/upload-text` | Ingest a pasted text snippet |
| `POST` | `/web/preview` | Fetch a URL and return extracted preview (no chunks written) |
| `POST` | `/web/ingest` | Fetch + ingest a URL into the session vector store |
| `PUT` | `/session/web-consent` | Toggle the per-session web-source consent flag |
| `POST` | `/suggest/batch` | Answer suggestions (single or multi-question, QTI-inspired input) |
| `POST` | `/suggest/stream` | Same as batch, streamed via Server-Sent Events |
| `GET` | `/session/stats` | Session status, TTL, document count, web flags |
| `DELETE` | `/session` | End session and delete all data |
| `GET` | `/audit-report` | Download session audit report (JSON or plaintext) |
| `GET` | `/privacy` | Data handling transparency statement |

Web ingestion is gated by two layers: the `CUE_WEB_INGEST_ENABLED` env flag
(operator) **and** a per-session `web_consent` toggle (respondent). Both
endpoints return HTTP 403 unless both are on. See [`docs/CUE_API.md`](../docs/CUE_API.md#add-a-web-source-url)
for the full preview/ingest payload shapes and the
[`OPERATOR_RUNBOOK.md`](../docs/OPERATOR_RUNBOOK.md#15-web-url-ingestion-off-by-default)
privacy decision checklist.

### POST /suggest/batch

Generate suggestions for multiple questionnaire items in a single request.
Items within the same section share context, improving suggestion quality
for related questions.

Accepts either a structured `sections` list or a flat `items` list — flat
items are normalised to an implicit single section internally.

**Supported question types:** `open_ended`, `single_choice`,
`multiple_choice`, `ranking`, `slider`

Full payload shapes and complete request/response JSON examples:
[`docs/CUE_API.md`](../docs/CUE_API.md) and
[`docs/examples/`](../docs/examples/).

## Configuration

Environment variables:

- `OPENROUTER_API_KEY` — OpenRouter API key for LLM access
- `CHROMA_BASE_PATH` — Path to ChromaDB storage (default: `/app/data/chroma`)
- `SESSION_TTL_HOURS` — Session expiration time (default: 24)
- `CUE_LLM_MODEL` — LLM model for Cue (default: `anthropic/claude-sonnet-4.6`). Docker-compose maps this to `LLM_MODEL` inside the container.

## Development

### Running Tests

```bash
# Run from repo root
pytest tests/ -v
```

### Dependencies

See root `requirements.txt` for full list. Key libraries:

- `fastapi` — Web framework
- `chromadb` — Vector database
- `markitdown` — Document extraction (beta)
- `openai` — LLM client (OpenAI-compatible)

## Privacy & Data Handling

- **Data retention**: All operational data (documents, vectors, metadata) deleted when session expires or user explicitly ends session
- **Audit reports**: Generated on session completion; user can download; auto-deleted after ~1 year if unclaimed
- **Consent**: User agrees to session terms at start (see EULA/privacy endpoint)
- **No training**: User documents never used to fine-tune or train models

## Citation Accuracy & Quality Metrics

Cue's core value is accurate, verifiable citations. Monitor:

- **Citation accuracy**: Do suggested answers actually come from cited sources?
- **Relevance**: Are retrieved passages actually useful for answering the question?
- **Completeness**: Do answers adequately address the question?

Manual review and LLM-based evaluation frameworks (e.g., RAGAS-style) planned for post-PoC refinement.

## Integration

Cue is designed as an embeddable SDK. Integrate via:

1. **REST API**: Call endpoints directly from existing survey/form tools
2. **QTI 3.0**: Import/export questionnaires in QTI format for interoperability
3. **Institutional SSO**: OAuth 2.0 integration with institutional identity providers

See [M-Shared](../m_shared/README.md) for client SDKs and utilities.

## References

- [Project Context](../openspec/project.md)
- [Shape Module](../shape_api/README.md)
- [M-Shared Utilities](../m_shared/README.md)
