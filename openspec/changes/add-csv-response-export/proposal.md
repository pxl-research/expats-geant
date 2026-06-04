# Change: Add CSV Response Export for LimeSurvey and Qualtrics

## Why

Today, sending completed responses back to the originating platform requires
live API access — RemoteControl 2 enabled on LimeSurvey, an API token on
Qualtrics. Many institutional admins will not enable RC2 or issue API tokens
for a pilot tool, which leaves respondents with a working AI co-pilot but no
path to deposit their answers anywhere.

Both LimeSurvey and Qualtrics ship first-class **file-based** response
importers in their admin UIs (LS: *Responses & statistics → Import responses
from CSV/Excel*; Qualtrics: *Data & Analysis → Import Responses*). We already
own the symmetric file-import path on the survey-definition side. Adding the
matching CSV-out for responses gives users a fully offline, no-API fallback
that maps onto the platform's existing UI.

## What Changes

- **Adapter contract.** Add an optional method
  `export_responses_to_csv(survey: Survey, responses: list[Response]) -> str`
  to `SurveyAdapter`, defaulting to `NotImplementedError`. Add a new
  capability string `"csv_export"` returned by adapters that implement it.
- **LimeSurvey adapter.** Implement `export_responses_to_csv` emitting the
  CSV shape consumed by *Responses → Import responses from CSV*: header row
  of `response_id`, `submitdate`, `lastpage`, `startlanguage`, `seed`, then
  one SGQA column per question (and per sub-question for `M`/`P` types),
  followed by one row per response. Reuses the SGQA-key construction from
  `submit_responses`.
- **Qualtrics adapter.** Implement `export_responses_to_csv` emitting the
  three-row Qualtrics import format: row 1 column IDs (`ResponseId`,
  `StartDate`, `EndDate`, `Status`, `Finished`, `QID...`), row 2 question
  text, row 3 the import-metadata JSON object Qualtrics expects, then one
  row per response.
- **Cue API.** Add `GET /responses/csv?platform={lss|qsf}` returning the CSV
  bytes as a downloadable attachment. Resolves the adapter, calls
  `export_responses_to_csv`, returns 400 if the adapter does not advertise
  `csv_export`, 404 if there are no responses yet.
- **Cue UI.** On the submission page, surface a "Download responses as CSV"
  button alongside (not in place of) the existing "Submit to platform"
  button when the active platform's adapter advertises `csv_export`. The
  CSV is offered as a download with a filename including the survey ID and
  timestamp.
- **Capability flag.** LimeSurvey and Qualtrics `capabilities()` return
  `{..., "csv_export"}`. QTI and SurveyMonkey do not (out of scope — neither
  platform offers a general-purpose CSV response import).

No breaking changes — the new method is additive on the base class, the new
endpoint is additive on the Cue API, and the new UI button is conditional on
the new capability flag.

## Impact

- Affected specs:
  - `questionnaire-design` — new `Response CSV Export` requirement; minor
    edit to the existing capability-discovery requirement to register
    `"csv_export"`.
  - `survey-ui` — new `CSV Response Download` requirement on the submission
    page.
- Affected code:
  - `m_shared/adapters/base.py` — abstract method + default NotImplementedError.
  - `m_shared/adapters/limesurvey.py` — implement `export_responses_to_csv`;
    update `capabilities()`.
  - `m_shared/adapters/qualtrics.py` — implement `export_responses_to_csv`;
    update `capabilities()`.
  - `cue_api/routes/responses.py` (or wherever `submit_responses` lives) —
    new `GET /responses/csv` endpoint.
  - `cue_ui/templates/submit.html` (or equivalent) + a small route handler —
    new download button + click handler.
  - Tests under `tests/test_adapters.py`, `tests/test_chat_adapters.py`,
    and `tests/test_cue_*`.
- Out of scope:
  - QTI and SurveyMonkey CSV export. QTI has a dedicated *QTI Results
    Reporting* XML format which is a separate proposal if/when an LMS
    integration partner asks for it. SurveyMonkey has no general CSV
    response importer on the tiers we target.
  - Automatic fallback from a failed `POST /submit` to a CSV download. See
    `design.md` for the rationale; we deliberately keep this an explicit
    user action.
