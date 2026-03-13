# survey-import Specification

## Purpose
TBD - created by archiving change add-live-api-import. Update Purpose after archive.
## Requirements
### Requirement: Fetch Survey from LimeSurvey API

The system SHALL support importing a survey directly from a LimeSurvey instance via the
RemoteControl 2 JSON-RPC API, given a base URL, admin username, admin password, and numeric
survey ID.

This feature is **security-sensitive**. Credentials are transmitted to the server and used
solely for the duration of the outbound API call. They MUST NOT be logged, persisted, or
included in any audit trail. File upload (`POST /surveys/import`) remains the recommended
path for all non-demo contexts.

#### Scenario: Successful LimeSurvey fetch

- **WHEN** valid credentials and a reachable LimeSurvey URL are provided with a known survey ID
- **THEN** the survey is fetched via RC2 `export_survey`, parsed, stored in the session,
  and the endpoint returns the same response shape as `POST /surveys/import`

#### Scenario: Missing credentials

- **WHEN** any of `api_url`, `username`, or `password` is absent
- **THEN** a 400 Bad Request error is returned

#### Scenario: Unreachable host or RC2 error

- **WHEN** the LimeSurvey instance cannot be reached or returns an RC2 error
- **THEN** a 502 Bad Gateway error is returned with an actionable message

---

### Requirement: Fetch Survey from Qualtrics API

The system SHALL support importing a survey directly from Qualtrics via the v3 Surveys API,
given an API token, datacenter ID, and survey ID.

This feature is **security-sensitive** under the same constraints as the LimeSurvey fetch
above.

#### Scenario: Successful Qualtrics fetch

- **WHEN** a valid API token, datacenter ID, and existing survey ID are provided
- **THEN** the survey definition is fetched via `GET /v3/surveys/{id}`, parsed, stored in
  the session, and the endpoint returns the same response shape as `POST /surveys/import`

#### Scenario: Missing credentials

- **WHEN** `api_token` or `datacenter_id` is absent
- **THEN** a 400 Bad Request error is returned

#### Scenario: API error or unreachable host

- **WHEN** the Qualtrics API returns a non-200 status or cannot be reached
- **THEN** a 502 Bad Gateway error is returned with an actionable message

#### Scenario: Unsupported format

- **WHEN** a format other than `lss` or `qsf` is submitted to `POST /surveys/import-from-api`
- **THEN** a 422 Unprocessable Entity error is returned

