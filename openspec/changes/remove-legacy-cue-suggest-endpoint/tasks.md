## 1. Remove endpoint and models

- [x] 1.1 Remove the `POST /suggest` handler from `cue_api/api.py`
- [x] 1.2 Remove `SuggestRequest`, `SuggestResponse`, and `CitationResponse` models from
        `cue_api/models.py`
- [x] 1.3 Remove the now-unused imports (`CitationResponse`, `SuggestRequest`,
        `SuggestResponse`) from `cue_api/api.py`

## 2. Update tests

- [x] 2.1 Remove `TestSuggestEndpoint` class from `tests/test_session_api.py`
- [x] 2.2 Remove the `/suggest` section of `TestSuggestAPIErrorBranches` from
        `tests/test_batch_suggest.py` (keep the `/suggest/batch` section)
- [x] 2.3 Update the module docstring in `tests/test_integration_batch.py` to remove
        the `POST /suggest` reference

## 3. Update e2e scripts

- [x] 3.1 `tests/scripts/e2e_chat_spot_check.py` — targets Shape API; its `/suggest`
        is unrelated and unchanged
- [x] 3.2 Update `tests/scripts/e2e_audit_spot_check.py` — replace `/suggest` calls with
        `/suggest/batch` single-item calls
- [x] 3.3 Update `tests/scripts/e2e_api_spot_check.py` — replace `/suggest` calls with
        `/suggest/batch` single-item calls

## 4. Update documentation

- [x] 4.1 Remove `POST /suggest` row from the endpoint table in `cue_api/README.md` and
        delete the `### POST /suggest` section
- [x] 4.2 Remove `POST /suggest` from the endpoint table and its full section in
        `docs/AUTOFILL_API.md`
- [x] 4.3 Update `docs/DEPLOYMENT.md` — replace the `/suggest` curl example with a
        `/suggest/batch` equivalent
- [x] 4.4 Update `docs/TESTING.md` — remove references to `/suggest` single-item tests
