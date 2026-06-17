## Context

LimeSurvey and Qualtrics both offer first-party file-based response import
in their admin UIs — LS reads CSV/Excel matching the SGQA column scheme;
Qualtrics reads a three-row-header CSV matching its survey QID scheme. These
importers exist independently of the platforms' write APIs and are typically
available even on accounts where the API is locked down for compliance or
licensing reasons. Adding a matching CSV-out path on our side lets a
respondent who finishes a Cue session in an air-gapped or restricted
environment still deposit the answers via the platform's admin UI.

Our existing `submit_responses` adapter method covers the API-based path.
The CSV-out path is a parallel, optional capability — not a replacement.

## Goals / Non-Goals

**Goals**
- One additional method on `SurveyAdapter` (`export_responses_to_csv`) and
  one new capability string (`"csv_export"`).
- Working CSV-out implementations for LimeSurvey and Qualtrics, verified
  against the running LS docker (LS 6.17.4 admin → import) and a Qualtrics
  sandbox.
- One Cue API endpoint and one Cue UI button.
- Test parity with the existing `submit_responses` paths: per-adapter
  column-shape tests + a round-trip test that re-parses the CSV we emit.

**Non-Goals**
- QTI Results Reporting XML — separate spec if/when needed.
- SurveyMonkey CSV import — not a general capability there.
- Automatic API-failure fallback to CSV.
- Excel (`.xlsx`) export. LS accepts both CSV and Excel; CSV is sufficient
  and avoids a binary dependency.
- Streaming export. Pilot response counts are modest (typically <500 per
  session); a single in-memory build is fine.

## Decisions

### Decision: New capability string, not overloading `"submit"`

`capabilities()` already exposes `"submit"` for the API write-back path.
Reusing it for CSV would conflate two operationally different paths (one
sends to the platform; one produces a download for the user to upload by
hand) and would break consumers that inspect capabilities to decide which
UI affordance to show.

Add `"csv_export"` as a distinct string. The Cue UI shows the CSV button
iff `"csv_export"` is present; the existing "Submit to platform" button
keeps its existing trigger condition.

**Alternatives considered**
- Single `"response_io"` umbrella capability — vague, makes the UI logic
  read worse.
- No capability flag; just `try: ... except NotImplementedError` — works
  but moves UI logic from declarative to exception-driven, which is the
  pattern we deliberately avoided when we added the existing capability set.

### Decision: Explicit "Download CSV" button, no automatic fallback

The CSV button is always offered as a separate action, never silently
substituted when `POST /submit` fails. An automatic fallback hides upstream
auth failures (the most common cause of `submit_responses` 502s in
practice) behind a download dialog, leaving the user to wonder what went
wrong and the admin to wonder why no responses arrived.

The cost is one extra button on a page that already has one. The benefit
is that error states stay legible and the user remains in control of
where their data goes.

**Alternatives considered**
- Auto-fallback on submit failure — rejected above.
- "Download CSV" replaces "Submit to platform" entirely on adapters where
  `csv_export` is present — rejected; loses the API path users *can*
  use when it works, and creates UX divergence between LS and a future
  adapter with only `"submit"`.

### Decision: CSV column shapes follow each platform's importer 1:1

**LimeSurvey** (matches *Responses → Import responses from CSV/Excel*):

```
response_id,submitdate,lastpage,startlanguage,seed,{sid}X{gid}X{qid},...
```

- Header columns: literally `response_id`, `submitdate`, `lastpage`,
  `startlanguage`, `seed`. (LS treats `response_id` as optional on import
  — we leave it blank and let LS assign.)
- One column per top-level question using the SGQA key
  `{sid}X{gid}X{qid}{title}` — exactly the form `submit_responses` already
  produces.
- For `M`/`P` multi-choice questions, one column per sub-question with the
  sub-question key appended: `{sid}X{gid}X{qid}{title}{subq_title}` (no
  brackets — same fix as issue #60).
- Values: option `value` for single-choice, `"Y"`/`""` for each
  multi-choice sub-question, plain string for text/numeric.

**Qualtrics** (matches *Data & Analysis → Import Responses*):

- Row 1: column IDs — fixed columns first (`ResponseId`, `StartDate`,
  `EndDate`, `Status`, `IPAddress`, `Progress`, `Duration`, `Finished`,
  `RecordedDate`, `ResponseId`, `DistributionChannel`, `UserLanguage`)
  followed by one column per question keyed `QID<n>` (or `QID<n>_<choice>`
  for multi-select).
- Row 2: human-readable question text — Qualtrics requires this row to
  exist; we copy the question text.
- Row 3: import-metadata JSON object — Qualtrics requires
  `{"ImportId":"QID...","timeZone":"UTC"}` for each column. We emit the
  minimum that satisfies the importer.
- Data rows 4..N: one per response.

These exact shapes are what each platform's documented importer expects;
deviation triggers "could not parse" errors with no useful detail. The
formats are stable across the LS 5+/6+ window and the Qualtrics v3 era.

### Decision: Tests

- Per-adapter unit tests assert the header row, the column order, and
  cell values for known fixtures.
- A round-trip test calls `import_survey` on a known LSS/QSF, attaches
  fixture responses, calls `export_responses_to_csv`, parses the result
  with stdlib `csv`, and asserts shape and values. No live network.
- A live-verification script (manual, not in CI) imports the emitted CSV
  into the LS 6.17.4 docker via the admin UI and asserts the row count
  appears in *Responses & statistics*. Mirrors the issue-#60 verification
  pattern.

## Risks / Trade-offs

- **Qualtrics three-row header is brittle.** The importer's error messages
  are vague. *Mitigation:* lock the format in code, gate it behind a
  round-trip test that we run before any change to the Qualtrics adapter.
- **LS `M`/`P` sub-question column naming has historically been a source
  of bugs (issue #60).** *Mitigation:* reuse the exact key construction
  from `submit_responses` rather than re-deriving — single source of truth.
- **Users may upload a CSV to the wrong survey.** *Mitigation:* the
  filename includes the platform survey ID
  (`responses-{platform}-{survey_id}-{timestamp}.csv`); the LS/Qualtrics
  importers also key on column IDs which will not match a different survey.
- **Encoding.** CSV emitted as UTF-8 with BOM (Qualtrics importer prefers
  it, LS tolerates it). Newlines `\r\n` per RFC 4180.

## Migration Plan

Additive only — no migration. The new method has a `NotImplementedError`
default, so existing adapters and call-sites are unaffected. The new
capability string is opt-in. The new UI button is conditional on the new
capability.

Rollback: revert the commit. No data lives outside the user's browser
download; the API endpoint can be removed without orphaning anything.

## Open Questions

- Should the Cue API endpoint require authentication, given the CSV
  contains the respondent's own answers? Default position: yes, same
  session-bound auth as `POST /submit`. Worth confirming.
- Should we redact respondent identifiers (if any) from the CSV before
  download, since the user may share it more freely than an API
  submission? Default position: emit as-is; the CSV is the user's own
  data, and adding redaction would diverge from what the platform's
  importer expects.

## Implementation Notes (added at apply time)

### Source of responses

The endpoint reads `review_state.json`, which is already maintained per-
keystroke by `cue_ui/static/review-state.js` (every textarea `input` event
and every radio/checkbox `change` event PUTs to `/review-state/{qid}`).
No new persistence is introduced; CSV-export and Submit become two views
over the same source of truth. Submit's body-driven path is now redundant
with `review_state.json` and can be migrated to read from it in a follow-up
change (out of scope here). This resolves the "404 if none yet" wording in
this change's proposal: it means "no `accepted` / `edited` entries in
`review_state.json`".

### Authentication

Resolved per design.md §Open Questions default position: the endpoint
inherits the existing session-bound JWT middleware that already protects
`/sessions/*`. Session ownership is checked via the same
`session_id != session.session_id` 403 pattern as `POST /submit`. No new
auth plumbing.

### Endpoint placement

Both endpoints (Submit + CSV download) live in `cue_api/routes/surveys.py`
because they share the same session-ownership, survey-load, adapter-
resolution and capability-gate scaffolding. A shared helper
`_question_meta_from_survey_data(survey_data)` builds the per-question
`_option_values` translation map and a sibling
`_responses_from_review_state(review_state, question_meta, session_id)`
converts persisted review entries to `list[Response]` — both helpers
strictly platform-agnostic, alongside the existing
`_build_responses_from_body`.

### Category C (SM / QTI) dead-end fix

Spec deltas already cover this in the "Neither affordance shown" scenario.
Implementation surfaces the existing JSON answer-report download as a
prominent primary-zone action labelled "Export your answers (JSON)" when
neither `"submit"` nor `"responses_export"` is advertised, instead of
leaving the review page as a literal dead end. No new endpoint; reuses
`/session/{id}/answer-report/download`.

### LimeSurvey SGQA column shape

The spec text says columns are keyed `{sid}X{gid}X{qid}{title}` for top-
level questions. The implementation emits `{sid}X{gid}X{qid}` to match what
`submit_responses` already produces — issue #60 verification proved this
shape works for both submit and CSV import; deviation here would break the
single-source-of-truth invariant the `_sgqa_key` helper is intended to
preserve.

### Live verification

Task §7.1 (LS) is verified against LS 6.17.4 via a live smoke that
generated the export, uploaded it through *Responses & statistics →
Import a VV response data file*, and observed the response count
go from N to N+1 with the expected sub-question selected. Task §7.2
(QSF, if a sandbox is available) intentionally stays open for the
operator.

### LimeSurvey actually has three response-related formats (discovered live)

The proposal's working assumption was "LS's CSV export shape IS what the
LS CSV importer accepts." That turned out to be wrong on two counts:

1. LS 6's admin response importer is the **VV** ("Vertical
   Verification") path — TAB-separated, distinct from CSV. We use a
   `_vv.csv` filename suffix to mirror LS's own `vvexport_{sid}.csv`
   naming style. It has two header rows
   and uses literal `{question_not_shown}` markers for empty cells.
2. LS has *three* incompatible response-format contracts, sharing no
   parsing code between them on the LS side:

   | Path | Column format | Sub-question separator |
   |---|---|---|
   | RC2 `add_response` (Submit) | `{sid}X{gid}X{qid}{sub_title}` | none (no brackets — issue #60) |
   | CSV export (read-only) | `{qcode}[{sub_qcode}]`, semicolons | brackets |
   | VV import (this change) | `{qcode}_{sub_qcode}`, TAB | underscore |

   These are independent contracts; matching one does not imply matching
   another. The proposal's "reuse the SGQA helper for the CSV emitter"
   intuition was therefore wrong — the CSV emitter must use VV column
   names, and the RC2 submit and VV import paths must keep their own
   column-naming functions.

Adapter naming reflects this — `export_responses_to_csv` was renamed to
`export_responses` and the return shape became `ResponseExport(content,
media_type, filename_suffix)` so each adapter can declare its native
format. The capability string is `responses_export`, not `csv_export`.

### Qualtrics: same risk vector, unverified

Qualtrics' CSV exporter and CSV importer formats almost certainly differ
the same way LS's do. Our shipped Qualtrics implementation matches the
documented importer contract (3-row CSV with `ImportId` JSON on row 3),
but we have no sandbox to run a live round-trip. The risk is captured
explicitly in the Qualtrics adapter's `export_responses` docstring and
task §7.2 stays open.
