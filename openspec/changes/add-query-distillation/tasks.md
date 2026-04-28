## 1. Query Distillation Method

- [ ] 1.1 Add `_distill_queries()` method to `RAGPipeline` — accepts a list of items (prompt, type, choices), section title, and document filenames; returns a dict mapping item ID → distilled query string
- [ ] 1.2 Implement JSON parsing of LLM response with fallback: if parsing fails or an item is missing from the response, use the original question text for that item
- [ ] 1.3 Add `CUE_QUERY_DISTILLATION` environment variable (default `true`); when `false`, skip distillation entirely
- [ ] 1.4 Add `CUE_DISTILLATION_BATCH_SIZE` environment variable (default `20`); sections larger than this are split into sub-batches

## 2. Integration into Batch Pipeline

- [ ] 2.1 Modify `suggest_batch()` to call `_distill_queries()` per section before the `_process_item` loop; pass distilled queries to `_process_item`
- [ ] 2.2 Modify `suggest_batch_stream()` similarly
- [ ] 2.3 Modify `_process_item()` to accept an optional `distilled_query` parameter; when provided, pass it to `retrieve()` instead of `item.prompt`
- [ ] 2.4 Ensure `item.prompt` (original text) is still used for `_generate_answer_with_reasoning()` and audit logging

## 3. Integration into Single-Question Path

- [ ] 3.1 Modify `suggest_answer()` to optionally distill the question before retrieval (single-item distillation, no batching)

## 4. Audit Logging

- [ ] 4.1 Add the distilled query as a field on the existing suggestion audit event in `_process_item()` and `suggest_answer()`
- [ ] 4.2 Unit test: verify the distilled query appears in audit log entries when distillation is enabled
- [ ] 4.3 Unit test: verify audit log entries use the original question text when distillation is disabled

## 5. Document Filename Access

- [ ] 5.1 Ensure `SessionManager` or `ChromaDocumentStore` exposes a method to list document filenames for a session (may already exist via session stats; verify and reuse)

## 6. Tests

- [ ] 6.1 Unit test `_distill_queries()`: verify correct JSON parsing, verify fallback on malformed output, verify empty/missing items handled
- [ ] 6.2 Unit test batch size splitting: verify sections exceeding `CUE_DISTILLATION_BATCH_SIZE` are split correctly
- [ ] 6.3 Unit test feature toggle: verify distillation is skipped when `CUE_QUERY_DISTILLATION=false`
- [ ] 6.4 Integration test: end-to-end batch suggestion with distillation enabled; verify suggestions are returned with citations
- [ ] 6.5 Integration test: verify fallback behaviour when distillation LLM call raises an exception

## 7. Configuration & Documentation

- [ ] 7.1 Add `CUE_QUERY_DISTILLATION` and `CUE_DISTILLATION_BATCH_SIZE` to `.env.example` with defaults and comments
- [ ] 7.2 Wire environment variables through `docker-compose.yml` for Cue service
- [ ] 7.3 Document the feature in `docs/CUE_API.md` (brief description under a "Query Distillation" subsection)

## 8. Validation

- [ ] 8.1 Run `openspec validate add-query-distillation --strict` and resolve any issues
- [ ] 8.2 Smoke test with a real survey: compare retrieval quality with and without distillation on a representative questionnaire
