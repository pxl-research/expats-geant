## ADDED Requirements

### Requirement: CSV Response Download

The survey submission page SHALL render a "Download responses as CSV" action alongside the existing "Submit to platform" action whenever the active platform's adapter advertises the `"csv_export"` capability. The download action SHALL invoke the Cue API CSV-export endpoint and present the result as a browser-initiated file download.

This is a deliberately user-initiated path — the UI MUST NOT substitute
the CSV download automatically when API submission fails, because doing
so would hide the upstream failure cause (typically authentication or
permissions) behind a download dialog.

#### Scenario: Both submit and CSV affordances shown

- **WHEN** the respondent reaches the submission page with an active
  platform whose adapter advertises both `"submit"` and `"csv_export"`
- **THEN** the page renders both a "Submit to platform" button and a
  "Download responses as CSV" button as peer actions

#### Scenario: Only CSV affordance shown

- **WHEN** the respondent reaches the submission page with an active
  platform whose adapter advertises `"csv_export"` but not `"submit"`
- **THEN** the page renders the "Download responses as CSV" button but
  not the "Submit to platform" button

#### Scenario: Neither affordance shown

- **WHEN** the active platform's adapter advertises neither `"submit"`
  nor `"csv_export"` (e.g., the file-import path with no platform target)
- **THEN** the page renders the existing answer-report download but no
  platform-bound action

#### Scenario: Successful CSV download

- **WHEN** the respondent clicks "Download responses as CSV"
- **THEN** the UI calls `GET /responses/csv?platform={platform}` and
  delivers the CSV as a browser download with a filename of the form
  `responses-{platform}-{survey_id}-{timestamp}.csv`

#### Scenario: API submission failure does not trigger CSV fallback

- **WHEN** the respondent clicks "Submit to platform" and the call fails
- **THEN** the UI surfaces the existing inline error and leaves the
  respondent's filled-in answers intact
- **AND** the UI does NOT automatically initiate a CSV download — the
  respondent must click the CSV button explicitly if they want that path
