## Context

Both LimeSurvey and Qualtrics already have adapter classes that handle credentials at
construction time and use them for `create_survey` and `submit_responses`. Adding a
`fetch_survey` method follows the same pattern without introducing any new credential
storage or session concept.

The existing `POST /surveys/import` endpoint parses a file the user uploads. The new
endpoint does the same thing, but retrieves the raw content from the platform API first.
The parsing, session storage, and response shape are identical.

## Goals / Non-Goals

- Goals:
  - Allow a survey to be fetched by ID directly from LimeSurvey or Qualtrics
  - Reuse existing adapter infrastructure and `import_survey()` parsers
  - Surface a clear security warning in the UI
- Non-Goals:
  - Storing or caching platform credentials
  - Supporting SurveyMonkey or QTI (file-only platforms)
  - Browsing or listing available surveys on the remote platform
  - Becoming an integration layer for production deployments

## Decisions

- **Credential scope**: Credentials are accepted in the JSON request body and passed
  directly to the adapter constructor. They are held in memory only for the duration of
  the request and never written to disk, logs, or the session store.

- **Endpoint shape**: A single `POST /surveys/import-from-api` endpoint with a
  discriminated body (format field selects which credential fields are required) keeps
  the API surface small. Alternative of separate `/import-from-limesurvey` and
  `/import-from-qualtrics` endpoints was rejected as unnecessary duplication.

- **LimeSurvey fetch mechanism**: RC2 `export_survey` returns a base64-encoded LSS XML
  string. Decoding it and passing to `import_survey()` reuses the full existing parser
  with no changes to the import path.

- **Qualtrics fetch mechanism**: `GET /v3/surveys/{id}` returns the survey definition as
  QSF-compatible JSON. The response body is serialised back to a JSON string and passed
  to `import_survey()`. No new parsing logic needed.

- **UI placement**: A second card on the existing upload page (below the file upload card)
  keeps the feature discoverable without requiring a new route. A prominent warning banner
  is shown before the credential fields.

## Risks / Trade-offs

- **Credential exposure**: User's platform credentials are sent to our server in plaintext
  (HTTPS assumed). This is the primary risk. Mitigated by: HTTPS-only deployment, no
  logging of credential fields, no persistence, and a visible UI warning.
- **Network reachability**: Self-hosted LimeSurvey instances may not be reachable from
  the server's network. The endpoint should return a clear 502 with an actionable message
  rather than a timeout.
- **LimeSurvey RC2 availability**: RC2 must be enabled by the administrator. If not,
  authentication will fail with a clear error.

## Open Questions

- Should the endpoint be disabled by a feature flag in production (`ENVIRONMENT=production`)?
  Currently leaning yes — same pattern as `/dev/token`.
