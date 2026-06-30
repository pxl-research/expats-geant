## ADDED Requirements

### Requirement: Fetch Survey from QuestionPro API

The system SHALL support importing a survey directly from QuestionPro via the v2 REST API, given an API key, a datacenter identifier, and a numeric survey ID.

This feature is **security-sensitive** under the same constraints as the LimeSurvey and Qualtrics fetch paths. The API key is transmitted to the server and used solely for the duration of the outbound API call. It MUST NOT be logged, persisted, or included in any audit trail. The datacenter identifier selects the regional base URL (`com`, `eu`, `ca`, `ae`, `com.au`, `surveyanalytics.com`, `gov.com`, `sa.com`); the base URL is computed as `https://api.questionpro.{datacenter_id}/a/api/v2`.

QuestionPro's API surface forces a two-step fetch: `GET /surveys/{id}` returns survey metadata, `GET /surveys/{id}/questions?page=&perPage=100` returns the paginated question list. The adapter SHALL exhaust the question pagination and assemble the result into a single `Survey` model. Sections SHALL be derived from `static_section_heading` markers in the QuestionPro question list (QuestionPro has no first-class section concept).

#### Scenario: Successful QuestionPro fetch

- **WHEN** a valid API key, datacenter ID, and existing survey ID are provided
- **THEN** the survey metadata is fetched via `GET /surveys/{id}`, the questions are fetched via paginated `GET /surveys/{id}/questions`, the result is assembled into a `Survey` with sections derived from `static_section_heading` boundaries, stored in the session
- **AND** the endpoint returns the same response shape as `POST /surveys/import`

#### Scenario: Missing credentials

- **WHEN** any of `api_key`, `datacenter_id`, or `survey_id` is absent
- **THEN** a 400 Bad Request error is returned naming the missing field

#### Scenario: Invalid datacenter ID

- **WHEN** `datacenter_id` is not one of the allowed values
- **THEN** a 400 Bad Request error is returned listing the allowed values

#### Scenario: Unreachable host or API error

- **WHEN** the QuestionPro instance cannot be reached or returns a non-2xx status
- **THEN** a 502 Bad Gateway error is returned with the QuestionPro response body included as actionable context

#### Scenario: Rate-limit response

- **WHEN** QuestionPro returns 429 Too Many Requests
- **THEN** the adapter performs one defensive retry honouring the `Retry-After` header (capped at 5 seconds)
- **AND** if the retry also returns 429, a 502 Bad Gateway is returned with a message naming the rate limit

#### Scenario: Unsupported format

- **WHEN** a format other than `lss`, `qsf`, or `questionpro` is submitted to `POST /surveys/import-from-api`
- **THEN** a 422 Unprocessable Entity error is returned
