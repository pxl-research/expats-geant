## ADDED Requirements

### Requirement: Response File Export via Adapter

Adapters that support file-based response export SHALL implement
`export_responses(survey: Survey, responses: list[Response]) -> ResponseExport`,
which returns a `ResponseExport` named tuple of `(content: bytes,
media_type: str, filename_suffix: str)`. The returned bytes SHALL be
importable into the originating platform's admin UI without further
transformation. The exact file format is adapter-defined — different
platforms accept different formats from their admin importers — and the
adapter declares it via the returned `media_type` and `filename_suffix`.

Adapters that do not support this path SHALL leave the method as the base
`NotImplementedError`. This capability is independent of `submit_responses`:
an adapter MAY implement either, both, or neither.

The export path is a deliberately offline fallback for environments where
the platform's API is not available. It is never substituted automatically
for an API submission; the caller chooses the path explicitly.

#### Scenario: LimeSurvey VV export

- **WHEN** `export_responses()` is called on the LimeSurvey adapter with a
  parsed survey and a list of responses
- **THEN** the returned bytes are TAB-separated (LS's "VV" — Vertical
  Verification — format, distinct from CSV; the filename ends in
  `_vv.csv` to mirror LS's own `vvexport_{sid}.csv` naming style)
- **AND** the file begins with TWO header rows: row 1 is human display
  labels, row 2 is the column codes the importer maps —
  `id`, `token`, `submitdate`, `lastpage`, `startlanguage`, `seed`,
  `startdate`, `datestamp` followed by one column per top-level question
  keyed by its user-defined code (`ls_qcode`) and one column per `M`/`P`
  sub-question keyed `{qcode}_{sub_qcode}` (UNDERSCORE separator)
- **AND** data rows encode single-choice answers as the option code,
  multi-choice selected sub-questions as `Y` (unselected as the literal
  `{question_not_shown}` marker), and text/numeric answers verbatim
- **AND** `media_type` is `text/tab-separated-values; charset=utf-8` and
  `filename_suffix` is `_vv.csv` (the suffix INCLUDES its leading
  connector — underscore — to mirror LS's own `vvexport_{sid}.csv` style)
- **AND** the file is importable by the LimeSurvey admin "Import a VV
  response data file" feature without further transformation

#### Scenario: Qualtrics CSV export

- **WHEN** `export_responses()` is called on the Qualtrics adapter with
  a parsed survey and a list of responses
- **THEN** the returned bytes are a UTF-8 CSV (with BOM) with three header
  rows: row 1 the Qualtrics column IDs (`ResponseId`, `StartDate`,
  `EndDate`, …, `QID<n>`, …), row 2 the human-readable question text, and
  row 3 the Qualtrics import-metadata JSON object per column
- **AND** the data rows starting at row 4 encode one response per row in
  the column order established by row 1
- **AND** `media_type` is `text/csv; charset=utf-8` and `filename_suffix`
  is `.csv`
- **AND** the CSV is importable by the Qualtrics "Import Responses" feature
  without further transformation

#### Scenario: Adapter without response export

- **WHEN** `export_responses()` is called on an adapter that does not
  implement it (QTI, SurveyMonkey)
- **THEN** `NotImplementedError` is raised with a message identifying the
  adapter and naming the `"responses_export"` capability the caller should
  check before invoking

#### Scenario: Empty response list

- **WHEN** `export_responses()` is called with an empty response list
- **THEN** the returned bytes contain only the platform's header row(s) —
  no data rows
- **AND** the file is still well-formed and importable (the platform's
  importer treats it as a zero-row import)

## MODIFIED Requirements

### Requirement: Adapter Capability Discovery

The system SHALL allow consumers to inspect what operations an adapter supports before invoking them. Each adapter SHALL return a set of capability strings from `capabilities()`. Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, `"responses_export"`. `"create"` indicates the adapter implements `create_survey()`; `"api_create"` additionally indicates that `create_survey()` pushes to a live platform API and returns a platform-assigned ID (as opposed to a file-export fallback). `"responses_export"` indicates the adapter implements `export_responses()` and the resulting bytes are consumable by the platform's first-party response importer (the file format is adapter-defined: LimeSurvey emits TSV in its VV shape; Qualtrics emits CSV).

#### Scenario: Adapter reports supported capabilities

- **WHEN** `capabilities()` is called on a LimeSurvey or Qualtrics adapter
- **THEN** it returns a set containing `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`, and `"responses_export"`

#### Scenario: Adapter reports limited capabilities

- **WHEN** `capabilities()` is called on a SurveyMonkey or QTI adapter
- **THEN** it returns a set containing `"import"`, `"export"`, and `"create"` but NOT `"submit"`, `"api_create"`, or `"responses_export"`

#### Scenario: created_via reflects actual creation path

- **WHEN** `POST /create` succeeds for a LimeSurvey or Qualtrics adapter
- **THEN** the response contains `created_via: "api"` and a platform-assigned survey ID
- **WHEN** `POST /create` succeeds for a SurveyMonkey or QTI adapter
- **THEN** the response contains `created_via: "file_export"` and serialized file content

#### Scenario: responses_export advertised independently of submit

- **WHEN** the UI inspects `capabilities()` to decide which response-output
  affordances to render
- **THEN** the presence of `"responses_export"` enables a download button
  and the presence of `"submit"` enables an API-submit button,
  independently — an adapter MAY advertise one without the other
