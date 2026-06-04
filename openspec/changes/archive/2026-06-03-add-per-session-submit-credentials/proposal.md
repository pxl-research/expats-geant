# Change: Collect Submit-to-Platform Credentials Per Session

## Why

Today the Cue API can submit completed responses back to LimeSurvey or
Qualtrics only if the **server operator** has pre-populated
`LIMESURVEY_API_URL` / `LIMESURVEY_USERNAME` / `LIMESURVEY_PASSWORD` (or
`QUALTRICS_API_TOKEN` / `QUALTRICS_DATACENTER_ID`) environment variables.
`GET /adapters/{format}/capabilities` strips the `"submit"` capability
whenever any of those env vars is missing, which hides the "Submit
Responses" button in the UI.

Consequently — even when the respondent has just imported a survey
**through the platform API** (and therefore proved they have valid
credentials), Cue offers no submit path. The credentials they supplied at
import time are correctly **not persisted** (matches the security
posture documented in `survey-import`), so they're gone by submit time
and there's no way to re-collect them.

The platform's API surface fully supports the submission (we use
LimeSurvey RC2 `add_response` and the Qualtrics Response Import API), and
the Shape UI already implements the symmetric collect-credentials-at-use
pattern for survey export. This proposal brings Cue's submit flow into
line.

## What Changes

- **Cue API.** `POST /sessions/{session_id}/submit` accepts an optional
  `credentials` object on the request body:
  - LimeSurvey: `{ api_url, username, password }`
  - Qualtrics: `{ api_token, datacenter_id }`
  The adapter is constructed per request using these fields; if no
  credentials are provided, the existing env-var fallback is used. This
  keeps existing pre-configured deployments working while unlocking
  per-session submission.
- **Cue API.** `GET /adapters/{format}/capabilities` SHALL no longer
  strip `"submit"` based on env-var presence. Capability advertising
  becomes purely a function of what the adapter actually implements;
  whether the *caller* has credentials to use it is decided at submit
  time, not at capability-discovery time.
- **Cue UI.** On the survey review page, when the active adapter
  advertises `"submit"`, the "Submit Responses" button SHALL open a
  credentials form gated to the same fields used during import (URL +
  username + password for LimeSurvey; API token + datacenter for
  Qualtrics). On successful submission the existing confirmation page
  is shown; on failure the existing inline error is shown with the
  respondent's answers preserved.
- **Security posture.** Submit credentials are subject to the same
  guarantee as import credentials: **transmitted to the server, used
  only for the duration of the outbound platform call, never logged
  and never persisted.** The credentials are sent over HTTPS as a JSON
  body on the same authenticated session that owns the responses.

No breaking changes — the env-var fallback is preserved. Deployments
that supply server-side credentials today continue to work without
configuration changes; the new credential fields are optional.

## Impact

- Affected specs:
  - `survey-ui` — modify the `Response Submission` requirement to cover
    the new credential prompt and the security guarantee (which mirrors
    the language already used in `survey-import`).
- Affected code:
  - `cue_api/models.py` — add an optional `credentials` field to the
    submit request model.
  - `cue_api/routes/surveys.py` — drop env-var gating from
    `get_adapter_capabilities`; thread caller-supplied credentials into
    `submit_session_responses` and `_adapter_credentials` (or its
    replacement).
  - `cue_ui/templates/survey.html` — add the credentials form panel,
    shown when the adapter advertises `"submit"` and submission is
    initiated.
  - `cue_ui/routes/review.py` — relay the new fields to the Cue API on
    submit.
  - Tests under `tests/test_cue_*` covering: credentials forwarded to
    adapter, env-var fallback when no credentials supplied, capabilities
    endpoint always returns `"submit"` for LS/Qualtrics regardless of
    env state, UI form rendering.
- Out of scope:
  - Storing credentials across sessions (out — same constraint that
    applies to import).
  - Browser-side credential autofill or password managers (out —
    standard HTML form semantics will pick this up automatically).
  - Two-factor or OAuth flows on the platform side (out — neither LS
    RC2 nor the Qualtrics token model exposes these).
