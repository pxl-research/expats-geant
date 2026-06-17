## 1. Adapter contract

- [x] 1.1 Add `export_responses(survey, responses) -> ResponseExport` to
  `SurveyAdapter` (default raises `NotImplementedError` with a clear
  message naming the adapter and capability). Define `ResponseExport`
  NamedTuple `(content: bytes, media_type: str, filename_suffix: str)`.
- [x] 1.2 Document the `"responses_export"` capability string in the
  adapter base-class docstring and in `docs/ADAPTERS.md`.

## 2. LimeSurvey implementation

- [x] 2.1 Implement `export_responses` emitting LS's VV-import shape
  (TAB-separated, two header rows, fixed prefix
  `id, token, submitdate, lastpage, startlanguage, seed, startdate,
  datestamp`, then `ls_qcode` columns for top-level questions and
  `{qcode}_{sub_qcode}` columns for M/P sub-questions; empty cells use
  the literal `{question_not_shown}` marker).
- [x] 2.2 Capture the question's user-defined code as `ls_qcode` on
  question metadata during import (both the LSS-XML path and the RC2
  `fetch_survey` path) so the export can address columns by code.
- [x] 2.3 Update `capabilities()` to include `"responses_export"`.
- [x] 2.4 Unit tests for two-header-row shape, fixed-column prefix,
  underscore sub-question separator, no brackets / no SGQA leak,
  single-choice value, multi-choice Y / `{question_not_shown}`,
  open-ended passthrough, empty-response edge case, id-auto-assign,
  startlanguage default.
- [x] 2.5 Round-trip parse: stdlib reader splits on TAB, asserts shape.

## 3. Qualtrics implementation

- [x] 3.1 Implement `export_responses` emitting the three-row Qualtrics
  importer format (column IDs, question text, ImportId JSON).
- [x] 3.2 Update `capabilities()` to include `"responses_export"`.
- [x] 3.3 Unit tests for header shape, multi-select column expansion,
  row-3 ImportId JSON validity, open-ended passthrough.
- [x] 3.4 Round-trip parse via stdlib `csv`.

## 4. Cue API endpoint

- [x] 4.1 Add `GET /sessions/{id}/responses/export?platform={lss|qsf}`
  to the Cue API.
- [x] 4.2 Resolve the adapter via the existing registry; 422 if the
  adapter does not advertise `"responses_export"`.
- [x] 4.3 Pull the session's responses from `review_state.json`; 404 if
  none yet.
- [x] 4.4 Return the adapter's `media_type` verbatim with a filename of
  `responses-{platform}-{survey_id}-{timestamp}.{filename_suffix}` via
  `Content-Disposition: attachment`.
- [x] 4.5 Integration tests covering success (LS + QSF), 403 session
  mismatch, 404 no-survey / no-answers, 422 unknown platform / missing
  capability, 400 platform mismatch.

## 5. Cue UI

- [x] 5.1 On the submission page, render a "Download responses for
  platform import" button alongside the existing submit button when the
  active platform's adapter advertises `"responses_export"`.
- [x] 5.2 Anchor link triggers a browser-driven download via the proxy
  route `/session/{id}/responses/export?platform=…`; on error display
  the existing alert pattern.
- [x] 5.3 Template/route test asserting the button is present only when
  the capability is advertised, plus a proxy-forwards-bytes-and-headers
  test.

## 6. Docs

- [x] 6.1 Add a short "Response Export" subsection to `docs/ADAPTERS.md`
  documenting the `"responses_export"` capability, the per-platform
  importer paths, and the format each adapter emits.
- [x] 6.2 Note in `docs/OPERATOR_RUNBOOK.md` that the download path is a
  no-API fallback usable when LS RC2 / Qualtrics tokens are not
  available.

## 7. Live verification

- [x] 7.1 Live LS smoke against LS 6.17.4: generate VV-format file via
  the refactored `LimeSurveyAdapter.export_responses`, upload through
  *Responses & statistics → Import a VV response data file*, observed
  response count 8 → 9 with only the expected sub-question (`QM1_A1` =
  Red) selected. The smoke also surfaced the import-vs-export format
  divergence captured in `design.md`.
- [ ] 7.2 Manually verify the Qualtrics CSV against a sandbox account
  (skip if no sandbox available; document the gap).
