# Change: Add Responses File Export for LimeSurvey and Qualtrics

## Why

Today, sending completed responses back to the originating platform requires
live API access — RemoteControl 2 enabled on LimeSurvey, an API token on
Qualtrics. Many institutional admins will not enable RC2 or issue API tokens
for a pilot tool, which leaves respondents with a working AI co-pilot but no
path to deposit their answers anywhere.

Both LimeSurvey and Qualtrics ship first-class **file-based** response
importers in their admin UIs:

- LimeSurvey: *Responses & statistics → Import a VV response data file*
  (LS's "VV" / Vertical Verification format — TAB-separated, two header
  rows, distinct from CSV; we use a `_vv.csv` filename suffix to mirror
  LS's own `vvexport_{sid}.csv` naming style).
- Qualtrics: *Data & Analysis → Import Responses* (three-row CSV).

We already own the symmetric file-import path on the survey-definition side.
Adding the matching out-side for responses gives users a fully offline,
no-API fallback that maps onto the platform's existing UI. The file format
is platform-specific; the adapter is the right layer to encode it.

## What Changes

- **Adapter contract.** Add an optional method
  `export_responses(survey: Survey, responses: list[Response]) -> ResponseExport`
  to `SurveyAdapter`, defaulting to `NotImplementedError`. `ResponseExport`
  is a small NamedTuple of `(content: bytes, media_type: str,
  filename_suffix: str)` so each adapter can declare the format the
  originating platform expects. Add a new capability string
  `"responses_export"` returned by adapters that implement it.
- **LimeSurvey adapter.** Implement `export_responses` emitting the VV
  shape consumed by *Import a VV response data file* (verified end-to-end
  against LS 6.17.4): TAB-separated, two header rows (display labels +
  column codes — `id, token, submitdate, lastpage, startlanguage, seed,
  startdate, datestamp` plus the question's `ls_qcode` for top-level and
  `{qcode}_{sub_qcode}` for `M`/`P` sub-questions, UNDERSCORE separator),
  then one row per response. Empty cells use the literal
  `{question_not_shown}` marker; multi-choice selected cells contain `Y`.
  Returns `(bytes, "text/tab-separated-values; charset=utf-8", "_vv.csv")`.
- **Qualtrics adapter.** Implement `export_responses` emitting the
  three-row Qualtrics import format: row 1 column IDs (`ResponseId`,
  `StartDate`, `EndDate`, `Status`, `Finished`, `QID...`), row 2 question
  text, row 3 the import-metadata JSON object Qualtrics expects, then one
  row per response. Returns `(bytes, "text/csv; charset=utf-8", "csv")`.
- **Cue API.** Add `GET /sessions/{id}/responses/export?platform={lss|qsf}`
  returning the adapter's bytes as a downloadable attachment with the
  adapter-declared `Content-Type` and a filename of the form
  `responses-{platform}-{survey_id}-{ts}.{suffix}`. Resolves the adapter,
  calls `export_responses`, returns 422 if the adapter does not advertise
  `responses_export`, 404 if there are no responses yet.
- **Cue UI.** On the submission page, surface a "Download responses for
  platform import" button alongside (not in place of) the existing "Submit
  to platform" button when the active platform's adapter advertises
  `responses_export`. The file is offered as a download with the adapter's
  declared format and filename.
- **Capability flag.** LimeSurvey and Qualtrics `capabilities()` return
  `{..., "responses_export"}`. QTI and SurveyMonkey do not (out of scope —
  neither platform offers a general-purpose file-based response import).

No breaking changes — the new method is additive on the base class, the new
endpoint is additive on the Cue API, and the new UI button is conditional on
the new capability flag.

## Impact

- Affected specs:
  - `questionnaire-design` — new `Response File Export` requirement;
    minor edit to the existing capability-discovery requirement to
    register `"responses_export"`.
  - `survey-ui` — new `Responses Export Download` requirement on the
    submission page.
- Affected code:
  - `m_shared/adapters/base.py` — `ResponseExport` NamedTuple, abstract
    method + default NotImplementedError.
  - `m_shared/adapters/limesurvey.py` — implement `export_responses`
    (VV/TSV); capture `ls_qcode` during import; update `capabilities()`.
  - `m_shared/adapters/qualtrics.py` — implement `export_responses`
    (CSV); update `capabilities()`.
  - `cue_api/routes/surveys.py` — new
    `GET /sessions/{id}/responses/export` endpoint, capability gate, and
    helper `_responses_from_review_state` shared with submit.
  - `cue_ui/templates/survey.html` + `cue_ui/routes/review.py` +
    `cue_ui/api_client.py` — download button, proxy route, client helper.
  - Tests under `tests/test_adapters.py`, `tests/test_session_api.py`,
    `tests/test_ui_routes.py`.
- Out of scope:
  - QTI and SurveyMonkey CSV export. QTI has a dedicated *QTI Results
    Reporting* XML format which is a separate proposal if/when an LMS
    integration partner asks for it. SurveyMonkey has no general CSV
    response importer on the tiers we target.
  - Automatic fallback from a failed `POST /submit` to a CSV download. See
    `design.md` for the rationale; we deliberately keep this an explicit
    user action.
