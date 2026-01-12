# Tasks: Implement M-Autofill RAG & Citation System

## 1. Implementation

- [ ] 1.1 Create `m_autofill/rag_pipeline.py` with semantic retrieval logic
  - [ ] 1.1a Query ChromaDB for top-k chunks matching question context
  - [ ] 1.1b Preserve and return metadata (source, position, timestamp)
  - [ ] 1.1c Handle edge cases (no results, malformed questions)
- [ ] 1.2 Implement answer generation function

  - [ ] 1.2a Accept retrieved chunks and question as inputs
  - [ ] 1.2b Call LLM client with temperature control (0.3-0.5 for determinism)
  - [ ] 1.2c Return generated answer text
  - [ ] 1.2d Handle LLM errors gracefully (retries, fallbacks)

- [ ] 1.3 Implement citation formatting & linking

  - [ ] 1.3a Extract source metadata from retrieved chunks
  - [ ] 1.3b Generate citation text with source name, position, timestamp
  - [ ] 1.3c Include exact text excerpt from source for verification
  - [ ] 1.3d Return citations as structured data (Citation model)

- [ ] 1.4 Integrate RAG pipeline components
  - [ ] 1.4a Create `suggest_answer(question, session_id)` function
  - [ ] 1.4b Orchestrate retrieval → generation → citation formatting
  - [ ] 1.4c Return structured result: (answer_text, citations, metadata)

## 2. Testing

- [ ] 2.1 Unit tests for semantic retrieval

  - [ ] 2.1a Test query against sample documents (ChromaDB)
  - [ ] 2.1b Verify metadata preservation
  - [ ] 2.1c Test edge cases (empty query, no results, session isolation)

- [ ] 2.2 Unit tests for answer generation

  - [ ] 2.2a Test LLM client invocation with temperature control
  - [ ] 2.2b Test graceful error handling (LLM timeout, API errors)
  - [ ] 2.2c Verify deterministic output consistency

- [ ] 2.3 Unit tests for citation formatting

  - [ ] 2.3a Test citation structure (source, position, timestamp, excerpt)
  - [ ] 2.3b Test text excerpt extraction from chunks
  - [ ] 2.3c Test edge cases (missing metadata, long excerpts)

- [ ] 2.4 Integration tests: RAG pipeline end-to-end
  - [ ] 2.4a Upload sample document → generate suggestion → verify citations
  - [ ] 2.4b Multiple documents → suggest answer → citations reference correct sources
  - [ ] 2.4c Session isolation: suggestions in session A don't leak to session B

## 3. Manual Testing & Validation

- [ ] 3.1 Citation accuracy review

  - [ ] 3.1a Spot-check 10-20 suggestions: do citations actually match sources?
  - [ ] 3.1b Target: ≥90% citation accuracy (citations are accurate and specific)
  - [ ] 3.1c Document any false or misleading citations

- [ ] 3.2 Answer quality review
  - [ ] 3.2a Are suggestions coherent and relevant to questions?
  - [ ] 3.2b Do suggestions appropriately summarize retrieved passages?
  - [ ] 3.2c Edge case testing: obscure questions, empty documents, noisy text

## 4. Documentation & Code Review

- [ ] 4.1 Add docstrings to `rag_pipeline.py` functions
- [ ] 4.2 Document RAG design decisions (temperature, top-k retrieval count, etc.)
- [ ] 4.3 Code review: verify code follows project conventions (PEP 8, type hints)
- [ ] 4.4 Update README in `m_autofill/` if needed

## Definition of Done

- ✅ All implementation tasks complete
- ✅ All unit tests passing (minimum: 20+ tests)
- ✅ All integration tests passing
- ✅ Manual testing confirms ≥90% citation accuracy
- ✅ No critical issues from code review
- ✅ Ready to hand off to 3.2 (audit logging)
