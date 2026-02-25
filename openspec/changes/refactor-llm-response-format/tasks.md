## 1. Prompt Update

- [x] 1.1 Update `_generate_answer_with_reasoning()` prompt in `rag_pipeline.py` to request JSON output
- [x] 1.2 Update single-question `suggest_answer()` to use the same JSON prompt format
- [x] 1.3 Ensure `selected` field is included in the prompt only for choice-type questions (unchanged logic, new format)

## 2. Parser Update

- [x] 2.1 Replace `_parse_structured_response()` with JSON-based parser
  - [x] 2.1a Strip markdown code fences before parsing
  - [x] 2.1b Parse with `json.loads()`
  - [x] 2.1c On parse failure, fall back to full response as `answer`, `null` for other fields, log warning
- [x] 2.2 Remove `_parse_structured_response()` block-collection logic (superseded)
- [x] 2.3 Update `_parse_selected_id()` callers if `selected` field handling changes (list vs string for multi-choice)

## 3. Tests

- [x] 3.1 Update `TestParseStructuredResponse` tests in `test_batch_suggest.py` for new JSON parser
- [x] 3.2 Add test: valid JSON with all fields present
- [x] 3.3 Add test: valid JSON with `selected` and `reasoning` null
- [x] 3.4 Add test: JSON wrapped in markdown fences is handled correctly
- [x] 3.5 Add test: malformed JSON falls back gracefully
- [x] 3.6 Add test: multi-line answer preserved in JSON value
- [x] 3.7 Verify existing integration tests (`test_integration_batch.py`) still pass

## 4. Validation

- [x] 4.1 Run full test suite and confirm no regressions
- [ ] 4.2 Manual spot-check with a real LLM call to verify JSON output in practice
