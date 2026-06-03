## 1. Cue API

- [x] 1.1 Add an optional `credentials` field to the submit request
  model (`cue_api/models.py`) with shape per platform: LS
  `{api_url, username, password}`, Qualtrics `{api_token, datacenter_id}`
- [x] 1.2 In `POST /sessions/{id}/submit`, resolve credentials in order:
  request body → env vars → 422
- [x] 1.3 Remove the env-var gating in `GET /adapters/{format}/capabilities`
  so it reports the adapter's true capability set
- [x] 1.4 Validate `api_url` via `validate_api_url` when supplied (same
  guard the import path uses) — offloaded to a thread because of DNS
- [x] 1.5 Ensure credentials never appear in logs (audit the new code
  paths against the existing structured logger calls)

## 2. Cue UI

- [x] 2.1 In `cue_ui/templates/survey.html`, when the active adapter
  advertises `"submit"`, render a credentials form (URL / username /
  password for LS, API token / datacenter for Qualtrics) gated to the
  Submit Responses action
- [x] 2.2 The form repeats the warning banner already used on the
  import page ("credentials are sent to this server and used
  immediately, never stored or logged")
- [x] 2.3 `cue_ui/routes/review.py` forwards the credential fields to
  the Cue API submit endpoint
- [x] 2.4 On submit failure, the inline error pattern already used for
  the submit flow is reused (no new error rendering code)

## 3. Tests

- [x] 3.1 Cue API test: credentials in body forwarded to adapter
  constructor
- [x] 3.2 Cue API test: no body credentials + env vars set → env vars
  used (regression for existing deployments)
- [x] 3.3 Cue API test: no body credentials + no env vars → 422 with
  actionable message
- [x] 3.4 Cue API test: capabilities endpoint reports `"submit"` for
  LS and Qualtrics regardless of env state
- [x] 3.5 Cue UI test: credential form renders when adapter advertises
  `"submit"`; does not render for QTI / SurveyMonkey
- [x] 3.6 Cue UI test: form submission flows the right field names
  through to the API

## 4. Docs

- [x] 4.1 Add a short subsection to `docs/ADAPTERS.md` noting the
  per-request credential pattern matches the import-from-API pattern
- [x] 4.2 Update `docs/OPERATOR_RUNBOOK.md`: the env-var path is now
  documented as the shared-account convenience, not the required path

## 5. Live verification

- [ ] 5.1 Against the LS 6.17.4 docker: import via API, complete the
  AI-assisted survey, click submit, supply credentials, verify the
  response appears in *Responses & statistics*
- [ ] 5.2 Manual Qualtrics sandbox verification if available;
  otherwise document the gap in the proposal close-out
