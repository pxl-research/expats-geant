## ADDED Requirements

### Requirement: Response CSV Export via Adapter

Adapters that support CSV-based response export SHALL implement
`export_responses_to_csv(survey: Survey, responses: list[Response]) -> str`,
which returns a UTF-8 CSV string in the exact column shape consumed by the
originating platform's first-party response importer (LimeSurvey's
*Responses → Import responses from CSV/Excel*; Qualtrics' *Data & Analysis
→ Import Responses*). The returned string SHALL be importable into the
target platform's admin UI without further transformation.

Adapters that do not support this path SHALL leave the method as the base
`NotImplementedError`. This capability is independent of `submit_responses`:
an adapter MAY implement either, both, or neither.

The CSV path is a deliberately offline fallback for environments where the
platform's API is not available. It is never substituted automatically for
an API submission; the caller chooses the path explicitly.

#### Scenario: LimeSurvey CSV export

- **WHEN** `export_responses_to_csv()` is called on the LimeSurvey adapter
  with a parsed survey and a list of responses
- **THEN** the returned CSV starts with the header row
  `response_id,submitdate,lastpage,startlanguage,seed` followed by one
  column per top-level question keyed `{sid}X{gid}X{qid}{title}`
- **AND** for each `M` or `P` multi-choice question, one column per
  sub-question keyed `{sid}X{gid}X{qid}{title}{subq_title}`
- **AND** the response rows encode single-choice answers as the option
  value, multi-choice answers as `Y` (selected) or empty (not selected)
  per sub-question, and text/numeric answers verbatim
- **AND** the CSV is importable by the LimeSurvey admin "Import responses
  from CSV/Excel" feature without further transformation

#### Scenario: Qualtrics CSV export

- **WHEN** `export_responses_to_csv()` is called on the Qualtrics adapter
  with a parsed survey and a list of responses
- **THEN** the returned CSV has three header rows: row 1 the Qualtrics
  column IDs (`ResponseId`, `StartDate`, `EndDate`, …, `QID<n>`, …), row 2
  the human-readable question text, and row 3 the Qualtrics import-metadata
  JSON object per column
- **AND** the data rows starting at row 4 encode one response per row in
  the column order established by row 1
- **AND** the CSV is importable by the Qualtrics "Import Responses" feature
  without further transformation

#### Scenario: Adapter without CSV export

- **WHEN** `export_responses_to_csv()` is called on an adapter that does
  not implement it (QTI, SurveyMonkey)
- **THEN** `NotImplementedError` is raised with a message identifying the
  adapter and naming the `"csv_export"` capability the caller should check
  before invoking

#### Scenario: Empty response list

- **WHEN** `export_responses_to_csv()` is called with an empty response
  list
- **THEN** the returned CSV contains only the header row(s) — no data rows
- **AND** the CSV is still well-formed and importable (the platform's
  importer treats it as a zero-row import)

## MODIFIED Requirements

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, `"csv_export"`. `"create"` indicates the adapter implements `create_survey()`; `"api_create"` additionally indicates that `create_survey()` pushes to a live platform API and returns a platform-assigned ID (as opposed to a file-export fallback). `"csv_export"` indicates the adapter implements `export_responses_to_csv()` and the resulting CSV is consumable by the platform's first-party response importer.

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, and `"csv_export"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"`, `"api_create"`, or `"csv_export"`

#### Scenario: created_via reflects actual creation path

- **WHEN** `POST /create` succeeds for a LimeSurvey or Qualtrics adapter
- **THEN** the response contains `created_via: "api"` and a platform-assigned survey ID
- **WHEN** `POST /create` succeeds for a SurveyMonkey or QTI adapter
- **THEN** the response contains `created_via: "file_export"` and serialized file content

#### Scenario: csv_export advertised independently of submit

- **WHEN** the UI inspects `capabilities()` to decide which response-output
  affordances to render
- **THEN** the presence of `"csv_export"` enables a download button and the
  presence of `"submit"` enables an API-submit button, independently — an
  adapter MAY advertise one without the other
