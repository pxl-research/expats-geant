## 1. Models & Parsing

- [ ] 1.0 Add `reasoning: Optional[str]` field to existing `SuggestResponse` in `m_autofill/api.py` (non-breaking, defaults to `null`)

- [ ] 1.1 Define `BatchSuggestRequest` Pydantic model (`assessment_id`, `context`, `sections`, `items`) in `m_autofill/models.py`
- [ ] 1.2 Define `BatchSuggestItem` model (`id`, `type`, `prompt`, `choices`)
- [ ] 1.3 Define `BatchSuggestResponse` model (`assessment_id`, `session_id`, `generated_at`, `model`, `responses`)
- [ ] 1.4 Define `ItemSuggestion` model (`item_id`, `type`, `suggestion`, `selected_id`/`selected_ids`, `reasoning`, `citations`)
- [ ] 1.5 Implement flat-to-sections normalization (wrap top-level `items` in implicit section)
- [ ] 1.6 Write unit tests for model validation and normalization logic

## 2. RAG Pipeline Extension

- [ ] 2.1 Add `suggest_batch` method to `RAGPipeline` in `m_autofill/rag_pipeline.py`
- [ ] 2.2 Implement section context injection (pass sibling question prompts to LLM system prompt)
- [ ] 2.3 Implement choice mapping: validate LLM-returned `selected_id` against input choices; fall back to `null` + remark if invalid
- [ ] 2.4 Ensure `reasoning` is elicited from LLM when `selected_id` is `null`, evidence is ambiguous, or answer synthesizes multiple sources; elicit on single endpoint too
- [ ] 2.5 Write unit tests for `suggest_batch` (mocked LLM, mocked retrieval)

## 3. API Endpoint

- [ ] 3.1 Add `POST /suggest/batch` endpoint to `m_autofill/api.py`
- [ ] 3.2 Wire request parsing, session lookup, RAG pipeline call, and response serialization
- [ ] 3.3 Add audit logging for batch suggest events (one event per item, or one batch event)
- [ ] 3.4 Write integration tests for full batch flow (upload → batch suggest → verify response structure)

## 4. Documentation

- [ ] 4.1 Update `m_autofill/README.md` with batch endpoint usage and example request/response
- [ ] 4.2 Add example input/output JSON files to `docs/` or `test_data/`
