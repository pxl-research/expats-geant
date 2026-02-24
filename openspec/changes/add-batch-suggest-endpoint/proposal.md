# Change: Add Batch Suggest Endpoint with Structured I/O

## Why

The current `POST /suggest` endpoint accepts a single question as plain text. Real questionnaires consist of related questions grouped in sections — context that is lost when questions are submitted individually. Sending a block of related questions together allows the LLM to reason across them, improving suggestion quality and reducing redundant retrieval. Additionally, there is currently no structured input or output format, making integration with external survey tools unnecessarily manual.

## What Changes

- New `POST /suggest/batch` endpoint accepting multiple questions in a single request
- QTI-inspired JSON input format (simplified subset) supporting flat item lists or grouped sections
- Structured JSON response format per question: human-readable suggestion, machine-parseable choice selection, LLM reasoning remark, and citations
- Section context injection: sibling question prompts passed as context during generation for each item in the same section
- New `interchange-formats` capability spec documenting the I/O standards, their origins, and migration paths
- Existing `POST /suggest` endpoint unchanged (single-question use cases remain valid)

## Impact

- Affected specs: `answer-suggestion` (extended), `interchange-formats` (new)
- Affected code: `m_autofill/api.py`, `m_autofill/rag_pipeline.py`
- New models: `m_autofill/models.py` (batch request/response Pydantic models)
- No breaking changes — additive only
