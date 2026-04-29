# Change: Add LLM-Based Query Rewriting for Cue RAG Retrieval

## Why

Cue's RAG pipeline currently passes the literal survey question text to ChromaDB for semantic search. Survey questions are often verbose, contain filler words, politeness framing, or instructions that dilute the semantic signal ("Could you please describe your current employment arrangement, including whether it is full-time, part-time, or contractual?"). This leads to suboptimal retrieval — relevant document chunks are missed or ranked lower than they should be.

An LLM-based query rewrite step before retrieval can strip framing, extract key concepts, and incorporate answer choices as search terms, producing tighter semantic search probes that match more relevant passages.

## What Changes

- Add a query rewrite step to `RAGPipeline` that rewrites survey questions into concise search queries before vector search
- Query rewrite uses the configured LLM client, with support for a dedicated rewrite model via `CUE_REWRITE_MODEL`
- Query rewrite is batched per section to amortize LLM call overhead and give the model thematic context; batch sizing is configurable via `CUE_REWRITE_BATCH_SIZE`
- Available context fed to the rewrite prompt: question text, question type, answer choices (for choice questions), section title, and document filenames from the session
- Feature is enabled by default but can be disabled via configuration (`CUE_QUERY_REWRITE=false`)
- Fallback: if query rewrite fails (LLM error, timeout, malformed output), the pipeline falls back to the original question text silently

## Impact

- Affected specs: `answer-suggestion` (modified retrieval flow)
- Affected code: `cue_api/rag_pipeline.py` (primary), `m_shared/llm/client.py` (per-call temperature override), `cue_api/api.py` (config wiring)
- No breaking changes to existing APIs or data models
- Slight increase in latency and token cost per suggestion batch (one additional LLM call per section)
