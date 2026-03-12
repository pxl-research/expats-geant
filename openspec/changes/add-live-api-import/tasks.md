## 1. Adapter — LimeSurvey fetch
- [ ] 1.1 Add `fetch_survey(survey_id: str) -> Survey` to `LimeSurveySurveyAdapter`:
        call RC2 `export_survey`, base64-decode result, pass to `import_survey()`
- [ ] 1.2 Raise `ValueError` if credentials not set; raise `RuntimeError` on RC2 error
        or network failure (include actionable message for unreachable hosts)

## 2. Adapter — Qualtrics fetch
- [ ] 2.1 Add `fetch_survey(survey_id: str) -> Survey` to `QualtricsSurveyAdapter`:
        call `GET /v3/surveys/{survey_id}`, serialise response to JSON string,
        pass to `import_survey()`
- [ ] 2.2 Raise `ValueError` if credentials not set; raise `RuntimeError` on non-200
        or network failure

## 3. API endpoint
- [ ] 3.1 Add `LiveApiImportRequest` Pydantic model to `m_autofill/api.py` (or models
        file): fields `format: str`, `survey_id: str`, plus optional credential fields
        (`api_url`, `username`, `password`, `api_token`, `datacenter_id`)
- [ ] 3.2 Add `POST /surveys/import-from-api` endpoint: validate format is `lss` or
        `qsf`, construct adapter with provided credentials, call `adapter.fetch_survey()`,
        store result to session (same path as file import), return same response shape
- [ ] 3.3 Map `ValueError` → 400, network/RC2 errors → 502 with descriptive message
- [ ] 3.4 Ensure credential fields are excluded from any request logging

## 4. UI — API client
- [ ] 4.1 Add `import_survey_from_api(token, session_id, format, survey_id, **credentials)`
        to `m_ui/api_client.py` calling `POST /surveys/import-from-api`

## 5. UI — upload page
- [ ] 5.1 Add "Import from Platform API" card to `upload.html` below the file upload card,
        including a prominent security warning (credentials sent to server)
- [ ] 5.2 Add format selector (limesurvey / qualtrics), with JS to show/hide the
        appropriate credential fields per selection
- [ ] 5.3 Add `POST /upload-from-api` route to `router.py`; call
        `api_client.import_survey_from_api()`, redirect to documents page on success,
        re-render form with error on failure

## 6. Tests
- [ ] 6.1 Unit tests for `LimeSurveySurveyAdapter.fetch_survey` (mock RC2 call)
- [ ] 6.2 Unit tests for `QualtricsSurveyAdapter.fetch_survey` (mock HTTP call)
- [ ] 6.3 API integration tests for `POST /surveys/import-from-api`:
        success (lss), success (qsf), missing credentials (400), unsupported format (422),
        platform unreachable (502)
