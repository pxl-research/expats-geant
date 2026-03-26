# Cue: Evidence-Based Answer Suggestion Assistant

An AI-powered respondent assistant that retrieves relevant passages from user documents, proposes concise answers with full citations, and transparently explains how suggestions were derived.

## Overview

Cue is a RAG (Retrieval-Augmented Generation) module that helps respondents complete surveys and forms more accurately and efficiently. When a respondent needs to answer a question, they can upload supporting documents (PDFs, Word docs, images, audio, video, or webpages). Cue:

1. **Retrieves**: Finds the most relevant passages from uploaded documents using semantic search
2. **Generates**: Proposes a concise draft answer informed by those passages
3. **Citations**: Shows exactly where information came from—line numbers, timestamps, highlights
4. **Explains**: Provides reasoning for why those sources were chosen

## Key Features

🔍 **Semantic Search & RAG**

- ChromaDB vector database for intelligent document retrieval
- Chunk-based storage with metadata (source, position, timestamp) for precise citations
- Multi-format support: PDF, DOCX, TXT, MD, PPTX, XLSX, XLS

📝 **Citation & Transparency**

- Full citation system: know which exact passages informed each answer
- Highlights and line numbers/percentages for easy document navigation
- Audit trail: why specific sources were retrieved and used

👤 **Privacy-First Design**

- Session-based isolation: each respondent session is independent
- Ephemeral storage: documents and vectors deleted after TTL expires (24-48h configurable)
- No profiling, no cross-session tracking
- GDPR-compliant with user consent capture

## Module Structure

```
cue_api/
├── __init__.py
├── api.py                   # FastAPI endpoints
├── ingest.py                # Document upload and ingestion pipeline
├── models.py                # Pydantic request/response models
├── rag_pipeline.py          # RAG orchestration: retrieval, generation, citations
├── rag_tools.py             # RAG tool wrappers for LLM tool calling
└── validation.py            # Input validation and sanitization
```

Tests live in the repo root `tests/` folder.

## RAG Pipeline Architecture

### Core Components

**1. Retrieval (`retrieve()`)**

- Semantic search using ChromaDB vector store
- Session-scoped: only searches documents within the user's session
- Returns top-k chunks (default: 5) with full metadata
- Metadata includes: source filename, chunk index, position/percentage, timestamp

**2. Answer Generation (`generate_answer()`)**

- LLM-based generation from retrieved passages
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

**4. Orchestration (`suggest_answer()`)**

- End-to-end pipeline: retrieve → generate → format citations
- Input validation (question, session_id)
- Returns structured result: `{answer, citations, metadata}`
- Handles edge cases: no documents, no results, session not found

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
| `POST` | `/suggest` | Single-question answer suggestion |
| `POST` | `/suggest/batch` | Multi-question batch suggestion (QTI-inspired input) |
| `POST` | `/suggest/stream` | Same as batch, streamed via Server-Sent Events |
| `GET` | `/session/stats` | Session status, TTL, document count |
| `DELETE` | `/session` | End session and delete all data |
| `GET` | `/audit-report` | Download session audit report (JSON or plaintext) |
| `GET` | `/privacy` | Data handling transparency statement |

### POST /suggest

Generate a suggestion for a single question.

**Request:**
```json
{
  "question": "What is our organisation's current data retention policy for employee records?",
  "context": "Completing a GDPR compliance questionnaire"
}
```

**Response:**
```json
{
  "answer": "Employee records are retained for 7 years after contract termination, in line with Belgian labour law requirements.",
  "reasoning": null,
  "citations": [
    {
      "source": "hr_policy_2024.pdf",
      "position": "62%",
      "position_range": {"start_percentage": 0.61, "end_percentage": 0.64},
      "timestamp": "2026-02-20T09:14:00Z",
      "excerpt": "employee personal data shall be retained for a period of seven years following termination"
    }
  ],
  "metadata": {}
}
```

### POST /suggest/batch

Generate suggestions for multiple questionnaire items in a single request. Items within the same section share context, improving suggestion quality for related questions.

Accepts either a structured `sections` list or a flat `items` list — flat items are normalized to an implicit single section internally.

**Supported question types:** `open_ended`, `single_choice`, `multiple_choice`, `ranking`, `slider`

**Request (sectioned):**
```json
{
  "assessment_id": "gdpr-compliance-2026",
  "context": "Annual GDPR compliance self-assessment for research institutions",
  "sections": [
    {
      "id": "s1",
      "title": "Data Retention",
      "items": [
        {
          "id": "q1",
          "type": "open_ended",
          "prompt": "Describe your organisation's data retention policy for research participant data."
        },
        {
          "id": "q2",
          "type": "single_choice",
          "prompt": "How long are research participant records retained after project completion?",
          "choices": [
            {"id": "c1", "label": "Less than 1 year"},
            {"id": "c2", "label": "1–3 years"},
            {"id": "c3", "label": "3–10 years"},
            {"id": "c4", "label": "More than 10 years"}
          ]
        }
      ]
    }
  ]
}
```

**Response:**
```json
{
  "assessment_id": "gdpr-compliance-2026",
  "session_id": "sess_abc123",
  "generated_at": "2026-02-24T10:30:00Z",
  "model": "openai/gpt-4o-mini",
  "responses": [
    {
      "item_id": "q1",
      "type": "open_ended",
      "suggestion": "Research participant data is retained for 5 years after project completion, consistent with the institution's research data management policy and funder requirements.",
      "selected_id": null,
      "selected_ids": null,
      "reasoning": null,
      "citations": [
        {
          "source": "rdm_policy_v3.pdf",
          "excerpt": "personal data collected during research projects shall be retained for a minimum of five years",
          "position": 0.34
        }
      ]
    },
    {
      "item_id": "q2",
      "type": "single_choice",
      "suggestion": "Research participant records are retained for 3–10 years after project completion.",
      "selected_id": "c3",
      "selected_ids": null,
      "reasoning": "The policy states a 5-year retention period, which falls within the 3–10 year bracket. Selected c3 accordingly.",
      "citations": [
        {
          "source": "rdm_policy_v3.pdf",
          "excerpt": "personal data collected during research projects shall be retained for a minimum of five years",
          "position": 0.34
        }
      ]
    }
  ]
}
```

See [`docs/examples/`](../docs/examples/) for complete request/response JSON files.

## Configuration

Environment variables:

- `OPENROUTER_API_KEY` — OpenRouter API key for LLM access
- `CHROMA_BASE_PATH` — Path to ChromaDB storage (default: `/app/data/chroma`)
- `SESSION_TTL_HOURS` — Session expiration time (default: 24)
- `LLM_MODEL` — Default model on OpenRouter (e.g., `anthropic/claude-haiku-4.5`)

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

## Roadmap

- ✅ Basic RAG pipeline (semantic search + LLM generation + citations)
- 🚧 Multi-format document support (audio/video transcription via MarkItDown)
- 🚧 Citation accuracy testing & refinement
- 📅 PostgreSQL integration for persistent metadata (future)
- 📅 Advanced re-ranking & filtering (future)

## References

- [Project Context](../openspec/project.md)
- [Shape Module](../shape_api/README.md)
- [M-Shared Utilities](../m_shared/README.md)
