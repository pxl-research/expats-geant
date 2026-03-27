# Change: Remove legacy POST /suggest endpoint from Cue API

## Why

`POST /suggest` is a limited legacy endpoint that only handles plain open-ended text with
no concept of question IDs, choice IDs, or structured input. `POST /suggest/batch` (and
`/suggest/stream`) already covers the single-question case — callers can pass a flat
`items` list with one item and get back a richer, structured response including
`item_id`, `selected_id`, `selected_ids`, and `reasoning`. Keeping two endpoints that
partially overlap causes confusion and maintenance overhead.

## What Changes

- **BREAKING**: `POST /suggest` (cue-api) is removed; callers MUST migrate to
  `POST /suggest/batch` with a flat single-item payload
- `SuggestRequest`, `SuggestResponse`, and `CitationResponse` Pydantic models removed
  from `cue_api/models.py`
- Unit and integration tests targeting `POST /suggest` removed or updated
- E2E spot-check scripts updated to use `POST /suggest/batch`
- Docs updated (`cue_api/README.md`, `docs/AUTOFILL_API.md`, `docs/DEPLOYMENT.md`,
  `docs/TESTING.md`)

## Impact

- Affected specs: `answer-suggestion`
- Affected code:
  - `cue_api/api.py` — endpoint handler removed
  - `cue_api/models.py` — three models removed
  - `tests/test_session_api.py` — `TestSuggestEndpoint` class removed
  - `tests/test_batch_suggest.py` — `/suggest` error-branch tests removed
  - `tests/test_integration_batch.py` — docstring updated
  - `tests/scripts/e2e_chat_spot_check.py`, `e2e_audit_spot_check.py`,
    `e2e_api_spot_check.py` — updated to use `/suggest/batch`
  - `cue_api/README.md`, `docs/AUTOFILL_API.md`, `docs/DEPLOYMENT.md`, `docs/TESTING.md`
- **Not affected**: `shape_api/api.py` has its own unrelated `POST /suggest` endpoint
  (questionnaire design tool) — that is a different service and is NOT changed
- **Not affected**: `cue_api/rag_pipeline.suggest_answer()` — the pipeline method is
  retained because it is used directly by integration and audit tests
