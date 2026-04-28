## 1. Query Rewrite Method

- [x] 1.1 Add `_rewrite_queries()` method to `RAGPipeline` — accepts a list of items (prompt, type, choices), section title, and document filenames; returns a dict mapping item ID → rewritten query string
- [x] 1.2 Implement JSON parsing of LLM response with fallback: if parsing fails or an item is missing from the response, use the original question text for that item
- [x] 1.3 Add `CUE_QUERY_REWRITE` environment variable (default `true`); when `false`, skip rewriting entirely
- [x] 1.4 Add `CUE_REWRITE_BATCH_SIZE` environment variable (default `20`); sections larger than this are split into sub-batches

## 2. Integration into Batch Pipeline

- [x] 2.1 Modify `suggest_batch()` to call `_rewrite_queries_for_section()` per section before the `_process_item` loop; pass rewritten queries to `_process_item`
- [x] 2.2 Modify `suggest_batch_stream()` similarly
- [x] 2.3 Modify `_process_item()` to accept an optional `rewritten_query` parameter; when provided, pass it to `retrieve()` instead of `item.prompt`
- [x] 2.4 Ensure `item.prompt` (original text) is still used for `_generate_answer_with_reasoning()` and audit logging

## 3. Integration into Single-Question Path

- [x] 3.1 Modify `suggest_answer()` to optionally rewrite the question before retrieval (single-item rewrite, no batching)

## 4. Audit Logging

- [x] 4.1 Add the rewritten query as a field on the existing suggestion audit event in `_process_item()` and `suggest_answer()`
- [x] 4.2 Unit test: verify the rewritten query appears in audit log entries when rewriting is enabled
- [x] 4.3 Unit test: verify audit log entries use the original question text when rewriting is disabled

## 5. Document Filename Access

- [x] 5.1 Ensure `SessionManager` or `ChromaDocumentStore` exposes a method to list document filenames for a session (reused existing `list_documents()` via `_get_document_names()` helper)

## 6. Tests

- [x] 6.1 Unit test `_rewrite_queries()`: verify correct JSON parsing, verify fallback on malformed output, verify empty/missing items handled
- [x] 6.2 Unit test batch size splitting: verify sections exceeding `CUE_REWRITE_BATCH_SIZE` are split correctly
- [x] 6.3 Unit test feature toggle: verify rewriting is skipped when `CUE_QUERY_REWRITE=false`
- [x] 6.4 Integration test: end-to-end batch suggestion with rewriting enabled; verify suggestions are returned with citations
- [x] 6.5 Integration test: verify fallback behaviour when rewrite LLM call raises an exception

## 7. Configuration & Documentation

- [x] 7.1 Add `CUE_QUERY_REWRITE` and `CUE_REWRITE_BATCH_SIZE` to `.env.example` with defaults and comments
- [x] 7.2 Wire environment variables through `docker-compose.yml` for Cue service
- [ ] 7.3 Document the feature in `docs/CUE_API.md` (brief description under a "Query Rewriting" subsection)

## 8. Dedicated Rewrite Model

- [x] 8.1 Add `CUE_REWRITE_MODEL` environment variable (optional; falls back to the primary LLM configuration when unset)
- [x] 8.2 Instantiate a second `LLMClient` for rewriting in `cue_api/api.py` when `CUE_REWRITE_MODEL` is set; pass to `RAGPipeline` constructor
- [x] 8.3 Add `CUE_REWRITE_MODEL` to `.env.example` and `docker-compose.yml`
- [x] 8.4 Unit test: verify rewriting uses the dedicated client when configured, and falls back to the main client when not

## 9. Validation

- [ ] 9.1 Run `openspec validate add-query-distillation --strict` and resolve any issues
- [ ] 9.2 Smoke test with a real survey: compare retrieval quality with and without rewriting on a representative questionnaire
