# M-Autofill: Evidence-Based Answer Suggestion Assistant

An AI-powered respondent assistant that retrieves relevant passages from user documents, proposes concise answers with full citations, and transparently explains how suggestions were derived.

## Overview

M-Autofill is a RAG (Retrieval-Augmented Generation) module that helps respondents complete surveys and forms more accurately and efficiently. When a respondent needs to answer a question, they can upload supporting documents (PDFs, Word docs, images, audio, video, or webpages). M-Autofill:

1. **Retrieves**: Finds the most relevant passages from uploaded documents using semantic search
2. **Generates**: Proposes a concise draft answer informed by those passages
3. **Citations**: Shows exactly where information came from—line numbers, timestamps, highlights
4. **Explains**: Provides reasoning for why those sources were chosen

## Key Features

🔍 **Semantic Search & RAG**

- ChromaDB vector database for intelligent document retrieval
- Chunk-based storage with metadata (source, position, timestamp) for precise citations
- Multi-format support: PDF, DOCX, TXT, images (OCR), audio (transcription), video

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
m_autofill/
├── __init__.py
├── ingest.py                # Document upload and ingestion pipeline
├── rag_pipeline.py          # RAG orchestration: retrieval, generation, citations
├── rag_tools.py             # RAG tool wrappers for LLM tool calling
├── validation.py            # Input validation and sanitization
├── api.py                   # FastAPI endpoints (Phase 3.3)
└── tests/
    ├── test_document_ingestion.py
    ├── test_chunking.py
    ├── test_rag_pipeline.py
    ├── test_rag_integration.py
    └── test_data/           # Sample documents for testing
```

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
# Unit tests (no API key required)
pytest tests/test_rag_pipeline.py -v

# Integration tests (requires API key)
OPENROUTER_API_KEY=your_key pytest tests/test_rag_integration.py -v
```

## API Endpoints

(Examples; final design TBD)

```
POST /sessions/{session_id}/documents/upload
  - Upload document(s) for a respondent session
  - Returns: document_id, chunk count, storage location

POST /sessions/{session_id}/suggest
  - Generate answer suggestion for a question
  - Input: question text, optional context
  - Returns: suggested_answer, citations (with source metadata), reasoning

GET /sessions/{session_id}/audit
  - Retrieve session audit report (reasoning, sources used, decisions)

DELETE /sessions/{session_id}
  - Explicitly end session and delete all data
```

## Configuration

Environment variables:

- `OPENROUTER_API_KEY` — OpenRouter API key for LLM access
- `CHROMADB_PATH` — Path to ChromaDB storage (default: temp directory)
- `SESSION_TTL_HOURS` — Session expiration time (default: 48)
- `LLM_MODEL` — Default model on OpenRouter (e.g., `openai/gpt-4`)

## Development

### Running Tests

```bash
pytest m_autofill/tests/ -v
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

M-Autofill's core value is accurate, verifiable citations. Monitor:

- **Citation accuracy**: Do suggested answers actually come from cited sources?
- **Relevance**: Are retrieved passages actually useful for answering the question?
- **Completeness**: Do answers adequately address the question?

Manual review and LLM-based evaluation frameworks (e.g., RAGAS-style) planned for post-PoC refinement.

## Integration

M-Autofill is designed as an embeddable SDK. Integrate via:

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
- [M-Chat Module](../m_chat/README.md)
- [M-Shared Utilities](../m_shared/README.md)
