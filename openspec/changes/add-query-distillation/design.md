## Context

Cue's RAG pipeline passes raw survey question text directly to ChromaDB for semantic search. Survey questions are often verbose or contain framing that reduces retrieval quality. Adding an LLM-based rewrite step before retrieval should improve the semantic match between queries and stored document chunks.

## Goals / Non-Goals

- Goals:
  - Improve retrieval relevance by rewriting survey questions into focused search queries
  - Leverage available context (choices, section title, document filenames) without adding significant latency
  - Graceful degradation: system works identically if rewriting fails or is disabled
  - Support a dedicated rewrite model (`CUE_REWRITE_MODEL`) for cost/latency optimization
- Non-Goals:
  - Multi-query fan-out (generating multiple variants and merging results) — single rewritten query per question
  - HyDE (Hypothetical Document Embeddings) — out of scope for this change

## Decisions

### Single rewritten query per question (not multiple variants)

Generating one focused search probe per question keeps retrieval cost at 1x (no additional ChromaDB queries). Multi-query fan-out with deduplication adds complexity and latency for uncertain benefit. Start simple; add fan-out later if retrieval quality still needs improvement.

### Batch rewriting per section with size bounds

Survey sections are the natural grouping. Batching questions gives the LLM thematic context (it sees the section title and sibling questions) and amortizes the LLM call cost. However, some surveys use a single section for all questions, so an upper bound prevents oversized prompts:

- **Lower bound**: 1 (a section with one question is rewritten alone)
- **Upper bound**: configurable via `CUE_REWRITE_BATCH_SIZE`, default 20 questions per LLM call; larger sections are split into sub-batches

### Context included in the rewrite prompt

| Context | Included | Rationale |
|---------|----------|-----------|
| Question text | Yes | Primary input |
| Question type | Yes | Signals what kind of answer to search for |
| Answer choices | Yes (choice questions) | Choice labels are excellent search terms |
| Section title | Yes | Lightweight thematic anchor |
| Document filenames | Yes | Hints at available content domain |
| Sibling prompts | No | Section title covers the theme; siblings add token cost without clear benefit for rewriting |
| Assessment-level context | No | Too vague; better used in generation phase |

### Prompt design

The rewrite prompt asks the LLM to produce one concise search query per question. It does not enforce brevity — a terse question like "Nationality?" may benefit from slight expansion ("nationality citizenship country of origin"), while a verbose question needs trimming. The prompt guides with "concise" and "to the point" without mandating shorter output.

Output format: JSON object mapping question IDs to rewritten queries (e.g. `{"q1": "..."}`) for structured parsing with fallback to original text on parse failure.

### Dedicated rewrite model

The rewrite step supports an optional dedicated LLM client via `CUE_REWRITE_MODEL`. When set, a separate `LLMClient` is created for rewriting. When unset, the primary LLM client is used. This allows operators to use a fast/cheap model (e.g. Gemini Flash) for the simple rephrasing task while keeping a stronger model for answer generation.

### Insertion point

The rewrite step inserts in `RAGPipeline` at the batch processing level (`suggest_batch` / `suggest_batch_stream`), rewriting all questions in a section before the per-item `_process_item` loop. The rewritten query is passed to `retrieve()` instead of the original prompt. The original prompt is still used for LLM generation (the generation step needs the full question context).

For the single-question `suggest_answer()` path, rewriting runs inline (single question, no batching benefit, but still useful for verbose questions).

## Risks / Trade-offs

- **Latency**: One additional LLM call per section batch (~0.3-1s with a fast model). Acceptable given that generation calls already dominate latency.
- **Token cost**: ~200-400 input tokens + ~100-200 output tokens per section batch. Marginal compared to generation costs.
- **LLM reliability**: Malformed JSON output from rewriting. Mitigated by fallback to original question text.
- **Over-reduction**: LLM strips too much context, producing a worse query than the original. Mitigated by keeping the prompt simple and testing with real survey data.

## Resolved Questions

### Log rewritten queries? — Yes

Log the rewritten query as a field on the existing suggestion audit event (not a separate event). This enables end-to-end diagnosis during the pilot: original question → rewritten query → retrieved chunks → answer. Negligible storage cost (one short string per question). If MLflow observability lands, attach the rewritten query as an attribute on the RAG trace span.

### Adjust distance threshold for rewritten queries? — No

Keep `max_citation_distance` unchanged at 1.5. Rewritten queries should produce better (lower-distance) matches, not different-scale distances. The threshold is a safety net for garbage results, not a quality filter. Changing it alongside rewriting would confound pilot evaluation by varying two things at once.
