## Context

The Cue submit endpoint exists, the LS and Qualtrics adapters'
`submit_responses` methods work, and the UI button is wired — but the
capability check at `cue_api/routes/surveys.py:222-223` discards
`"submit"` unless server-side env vars are populated, so the button
never appears. The existing env-var path was designed for a single-
operator deployment where one shared platform account services all
respondents. That was a reasonable MVP choice but it doesn't fit the
self-service flow the import-from-API path encourages.

The import-from-API path already collects credentials in a form,
forwards them on a single outbound call, and never persists them. This
proposal extends that exact pattern to the submit path.

## Goals / Non-Goals

**Goals**
- Make submit-to-platform reachable for users who imported via the
  platform API, with no server-side credential configuration.
- Preserve the existing env-var fallback so operators with a shared
  account need no change.
- Preserve the "credentials never persisted" guarantee.
- Match the look-and-feel of the existing import-from-API credential
  form so users recognise the pattern.

**Non-Goals**
- Persisting credentials anywhere — neither on disk, in session
  metadata, nor in a vault. Each submit request supplies its own.
- Pre-validating credentials at form-submit time. The platform's own
  error from `submit_responses` is the source of truth; a separate
  pre-check would add complexity and lag.
- Caching credentials in the browser beyond what HTML form semantics
  + the browser's own password manager naturally provide.

## Decisions

### Decision: Optional credentials on the request, env-var fallback preserved

The `POST /sessions/{id}/submit` body gains an optional `credentials`
object. The endpoint resolves credentials in this order:

1. Request body `credentials` — if present and complete, use these.
2. Environment variables — `LIMESURVEY_*` / `QUALTRICS_*`. If complete,
   use these.
3. Otherwise → 422 with a message indicating credentials are required.

This means existing deployments with the env vars set today need no
config change; new deployments use the request-body path. The
preferred path for new self-service flows is the request body — env
vars are documented as a legacy/shared-account convenience.

**Alternatives considered**
- Remove env vars entirely. Cleaner code, breaks existing operators.
  Rejected.
- Require credentials on every request. Cleanest model, breaks
  existing operators. Rejected.

### Decision: Stop env-gating the capability endpoint

`GET /adapters/{format}/capabilities` returns what the adapter
*supports*, not what the current server *can use*. Today's behaviour
conflates those two questions, which is exactly why the UI hides the
button: the *adapter* supports submit (LS implements
`submit_responses`) but the *server* might lack credentials, so the
capability is stripped.

Decision: report the adapter's true capabilities. The UI knows the
adapter supports submit and can render the affordance + credential
form. The submit call itself is the place where missing credentials
turn into a 422.

This may surface a UI affordance that the user can't immediately use
(if they have no credentials), but the credential form is the obvious
way to resolve that — the same way the Import-from-Platform card on
the upload page does today.

### Decision: One form panel, conditional on adapter

The submit credentials form is rendered alongside the Submit button,
disclosed when the user initiates submit (modal or inline panel —
implementation detail, both are acceptable). The form fields mirror
the import-from-API form exactly:

- LimeSurvey: API URL (`type=url`), Username, Password.
- Qualtrics: API Token (`type=password`), Datacenter ID.

`autocomplete` attributes set to `current-password` / `username` so the
browser's password manager can offer the same entry the user typed at
import time, with no extra plumbing.

### Decision: Tests

- API tests: credentials forwarded → adapter constructed with those
  fields; no credentials + env vars set → adapter constructed with env
  vars; no credentials + no env vars → 422; capabilities endpoint
  reports `"submit"` for LS/Qualtrics regardless of env state.
- UI route tests: credential form rendered when adapter advertises
  submit; form not rendered when it does not (QTI, SurveyMonkey).
- Live verification against the running LS docker: paste credentials,
  click submit, observe response row in *Responses & statistics*.

## Risks / Trade-offs

- **Misleading capability advertisement.** The capability endpoint
  reports submit-supported even when no creds are available locally.
  *Mitigation:* the UI's submit affordance opens a credential form, so
  the user has an obvious path to supply them. Documented in
  `survey-ui`.
- **Credentials in transit.** They flow over the same authenticated
  session channel as everything else. *Mitigation:* HTTPS-only in
  production (the existing `validate_api_url` and CORS rules already
  enforce this); never logged (existing logging guidelines apply
  unchanged); never stored.
- **Clipboard / form residue.** A credentials form leaves traces in
  the browser. *Mitigation:* same risk as the existing import flow —
  consistent posture across both ends, called out in the UI warning
  banner that we already render on the import form.

## Migration Plan

Additive only — no data migration. Existing deployments with env vars
configured continue to work; the new credential fields are optional.
The capability-endpoint change is observable to clients that read
capabilities, but the only relevant client is the Cue UI which we
update in lockstep.

Rollback: revert the commit. No persisted state changes.

## Open Questions

- Should the submit form preserve the import-time URL as a default
  (read from the original form via session state) without the
  username/password parts? The URL is not security-sensitive on its
  own. *Default position:* no — keep the submit form fully empty,
  consistent with the import form's behaviour on a fresh page. Worth
  confirming with a quick UX check.
