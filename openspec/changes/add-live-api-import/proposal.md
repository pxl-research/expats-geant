# Change: Add Live Survey Import from Platform APIs

## Why

Users sometimes want to import a survey directly from their LimeSurvey or Qualtrics
instance without first exporting a file. The adapters already have the HTTP machinery
and credential model needed to support this; adding a fetch method to each adapter and
a thin API endpoint makes live import possible with minimal new code.

**File upload remains the preferred path.** This feature is security-sensitive: the
user's platform credentials are transmitted to and briefly handled by our server. It is
provided as a convenience for demo and pilot use, not as an integration pattern for
production deployments. Production integrators should call their platform APIs themselves
and POST the resulting file to `POST /surveys/import`.

## What Changes

- `LimeSurveySurveyAdapter.fetch_survey(survey_id)` — calls RC2 `export_survey`, decodes
  base64 LSS XML, feeds to existing `import_survey()`
- `QualtricsSurveyAdapter.fetch_survey(survey_id)` — calls `GET /v3/surveys/{id}`, feeds
  JSON response to existing `import_survey()`
- `POST /surveys/import-from-api` endpoint on m-autofill — accepts credentials + survey ID
  + format, delegates to adapter, stores result identically to `POST /surveys/import`
- New `import_survey_from_api()` method on `m_ui/api_client.py`
- New "Import from Platform API" section on the upload page with a security warning,
  format selector, and conditional credential fields
- Supported platforms: **LimeSurvey** and **Qualtrics** only (SurveyMonkey and QTI are
  file-only; no live API for them)

## Impact

- Affected specs: `survey-import` (new capability), `survey-ui`
- Affected code: `m_shared/adapters/limesurvey.py`, `m_shared/adapters/qualtrics.py`,
  `m_autofill/api.py`, `m_ui/api_client.py`, `m_ui/router.py`,
  `m_ui/templates/upload.html`
- No breaking changes; `POST /surveys/import` (file upload) is unchanged
- Credentials are never logged, never persisted, and used only for the duration of the
  outbound API call
