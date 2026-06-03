## MODIFIED Requirements

### Requirement: Response Submission

When the respondent submits the completed form, the UI SHALL send all responses to the Cue API, which delegates to the adapter's `submit_responses()`. The UI SHALL display a clear success or error state after the submission attempt.

When the active adapter advertises the `"submit"` capability, the UI SHALL render a credentials form gated to the Submit Responses action — the same fields used by the import-from-API flow on the upload page (API URL + username + password for LimeSurvey; API token + datacenter for Qualtrics). These credentials are forwarded to the Cue API on the submit request and are subject to the same security guarantee as import-time credentials: transmitted to the server, used only for the duration of the outbound platform call, never logged, never persisted.

If the Cue API has server-side environment credentials configured for the active platform, the credential form is still rendered but the request-body credentials take precedence when supplied. This preserves the existing shared-account deployment pattern while supporting per-session credentials.

#### Scenario: Successful submission with per-session credentials

- **WHEN** the respondent clicks submit, supplies platform credentials in the form, and all required questions are answered
- **THEN** the UI POSTs the responses and credentials to the Cue submit endpoint
- **AND** displays a confirmation page on success
- **AND** the credentials are not stored in the browser beyond the form lifetime or sent in any subsequent request

#### Scenario: Successful submission with server-side fallback credentials

- **WHEN** the deployment has `LIMESURVEY_*` or `QUALTRICS_*` environment credentials configured AND the respondent clicks submit without filling in the form fields
- **THEN** the Cue API uses the server-side credentials to invoke `submit_responses()`
- **AND** the UI displays a confirmation page on success

#### Scenario: Submission error

- **WHEN** the submit call fails (network error, platform API error, or invalid credentials)
- **THEN** the UI displays an error message without losing the respondent's filled-in answers
- **AND** allows the respondent to retry, including amending the credentials

#### Scenario: Credentials form not shown for adapters without submit support

- **WHEN** the active adapter does not advertise the `"submit"` capability (QTI, SurveyMonkey)
- **THEN** the UI does not render the Submit Responses action or the credentials form, and the display-only banner from `survey-import` remains in effect
