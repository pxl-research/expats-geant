## ADDED Requirements

### Requirement: Responses Export Download

The survey submission page SHALL render a "Download responses for platform import" action alongside the existing "Submit to platform" action whenever the active platform's adapter advertises the `"responses_export"` capability. The download action SHALL invoke the Cue API responses-export endpoint and present the result as a browser-initiated file download. The exact file format is adapter-defined (e.g. LimeSurvey emits TSV in its VV shape; Qualtrics emits CSV); the UI MUST forward the adapter's declared `media_type` and filename suffix verbatim and MUST NOT assume "CSV" in user-facing copy or in the Content-Type header.

This is a deliberately user-initiated path — the UI MUST NOT substitute the response-file download automatically when API submission fails, because doing so would hide the upstream failure cause (typically authentication or permissions) behind a download dialog.

#### Scenario: Both submit and export affordances shown

- **WHEN** the respondent reaches the submission page with an active
  platform whose adapter advertises both `"submit"` and `"responses_export"`
- **THEN** the page renders both a "Submit to platform" button and a
  "Download responses for platform import" button as peer actions

#### Scenario: Only export affordance shown

- **WHEN** the respondent reaches the submission page with an active
  platform whose adapter advertises `"responses_export"` but not `"submit"`
- **THEN** the page renders the "Download responses for platform import"
  button but not the "Submit to platform" button

#### Scenario: Neither affordance shown

- **WHEN** the active platform's adapter advertises neither `"submit"`
  nor `"responses_export"` (e.g., the file-import path with no platform target)
- **THEN** the page renders the existing answer-report download but no
  platform-bound action

#### Scenario: Successful responses-export download

- **WHEN** the respondent clicks "Download responses for platform import"
- **THEN** the UI calls `GET /sessions/{id}/responses/export?platform={platform}`
  and delivers the bytes as a browser download with a filename of the form
  `responses-{platform}-{survey_id}-{timestamp}{suffix}`, where
  `{suffix}` includes its own leading connector and comes from the adapter
  (e.g. `_vv.csv` for LimeSurvey, `.csv` for Qualtrics)
- **AND** the response carries the adapter's declared `Content-Type`
  verbatim (e.g. `text/tab-separated-values` for LimeSurvey, `text/csv`
  for Qualtrics)

#### Scenario: API submission failure does not trigger export fallback

- **WHEN** the respondent clicks "Submit to platform" and the call fails
- **THEN** the UI surfaces the existing inline error and leaves the
  respondent's filled-in answers intact
- **AND** the UI does NOT automatically initiate the responses-export
  download — the respondent must click the export button explicitly if
  they want that path
