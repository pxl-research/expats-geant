# Change: Implement M-Autofill RAG & Citation System

## Why

M-Autofill's core value is evidence-based answer suggestions grounded in user-uploaded documents. Without a functional RAG (Retrieval-Augmented Generation) pipeline and citation system, users cannot trust suggestions or trace their origin. This change implements the retrieval and answer generation logic, along with precise citations that show which document passages informed each suggestion.

## What Changes

- **RAG Pipeline:** Semantic vector search (ChromaDB) retrieves relevant document chunks for a given question, then LLM generates an answer based on those passages
- **Citation System:** Citations include source metadata (filename, position/percentage, timestamp) and exact text excerpts for user verification
- **Answer Generation:** Temperature-controlled LLM calls for consistent, slightly deterministic output
- **No external changes:** This is internal to M-Autofill; no API or schema changes in this phase

**Breaking Changes:** None

## Impact

- **Affected specs:**
  - `specs/answer-suggestion/spec.md` (requirements for retrieval, generation, citations)
  - `specs/llm-integration/spec.md` (LLM client already exists; we use it)
  - `specs/vector-db/spec.md` (ChromaDB client already exists; we use it)
  - `specs/data-models/spec.md` (Citation data model already exists; we enhance/use it)
- **Affected code:**

  - `m_autofill/rag_pipeline.py` (new; core RAG logic)
  - `m_autofill/validation.py` (existing; used for input validation)
  - `m_shared/models/citation.py` (existing; enhanced for citation formatting)
  - `m_shared/llm/client.py` (existing; used for generation)
  - `m_shared/vectordb/client.py` (existing; used for retrieval)

- **New dependencies:** None (LLM and vector DB clients already exist from Phase 1–2)

## Timeline

- **Estimated duration:** 2–3 weeks (Mar, Week 1-2)
- **Blockers:** None; depends only on Phase 1 & 2 (both complete)

## Implementation Approach

1. Implement semantic retrieval: Query ChromaDB for top-k chunks, preserve metadata
2. Implement answer generation: Pass retrieved chunks to LLM with temperature control
3. Implement citation formatting: Extract source metadata, highlight relevant text
4. Write comprehensive unit tests for each component
5. Manual testing: Verify citation accuracy and answer relevance (≥90% citation accuracy target)
