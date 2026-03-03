# Change: Refactor LLM Response Format to JSON

## Why

The RAG pipeline currently asks the LLM to respond using a custom plain-text prefix format (`ANSWER:`, `SELECTED:`, `REASONING:`). This format is fragile: LLMs do not reliably follow custom text protocols, multi-line values require special block-collection parsing, and any deviation (unexpected whitespace, markdown formatting, different capitalisation) causes silent data loss. A structured JSON response is unambiguous, natively handles multi-line values, and produces a detectable parse error on failure rather than silently dropping content.

Additionally, the single-question (`POST /suggest`) and batch (`POST /suggest/batch`) endpoints currently use different prompt formats, creating inconsistency in LLM interaction patterns across the codebase.

## What Changes

- Replace the `ANSWER:/SELECTED:/REASONING:` prefix format with a JSON response instruction in the LLM prompt
- Replace `_parse_structured_response()` with `json.loads()` + graceful fallback
- Align `suggest_answer()` (single endpoint) with the same prompt format as `suggest_batch()`
- Strip markdown code fences (` ```json ... ``` `) that some models wrap around JSON output
- On JSON parse failure, fall back gracefully: treat full response as `answer`, set `selected` and `reasoning` to `null`

## Impact

- Affected specs: `answer-suggestion` (prompt format, parsing, fallback behaviour)
- Affected code: `m_autofill/rag_pipeline.py` — `_generate_answer_with_reasoning()`, `_parse_structured_response()`
- No API contract changes — request/response schemas are unchanged
- No breaking changes for callers
