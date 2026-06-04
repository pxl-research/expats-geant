## 1. Adapter contract

- [ ] 1.1 Add `export_responses_to_csv(survey, responses) -> str` to
  `SurveyAdapter` (default raises `NotImplementedError` with a clear
  message naming the adapter and capability)
- [ ] 1.2 Document the `"csv_export"` capability string in the adapter
  base-class docstring and in `docs/ADAPTERS.md`

## 2. LimeSurvey implementation

- [ ] 2.1 Implement `export_responses_to_csv` emitting the
  documented LS importer CSV shape (header + SGQA columns + sub-question
  columns for M/P)
- [ ] 2.2 Reuse the SGQA-key helper from `submit_responses` (do not
  re-derive)
- [ ] 2.3 Update `capabilities()` to include `"csv_export"`
- [ ] 2.4 Unit tests for header row, column order, single-choice values,
  multi-choice Y/empty values, open-ended text passthrough, empty-response
  edge case
- [ ] 2.5 Round-trip test: import a fixture LSS, attach fixture responses,
  emit CSV, re-parse with stdlib `csv`, assert shape

## 3. Qualtrics implementation

- [ ] 3.1 Implement `export_responses_to_csv` emitting the three-row
  Qualtrics importer format (column IDs, question text, ImportId JSON)
- [ ] 3.2 Update `capabilities()` to include `"csv_export"`
- [ ] 3.3 Unit tests as in 2.4 plus a test that the row-3 ImportId JSON
  parses as valid JSON and contains a `QID*` for every data column
- [ ] 3.4 Round-trip test analogous to 2.5

## 4. Cue API endpoint

- [ ] 4.1 Add `GET /responses/csv?platform={lss|qsf}` to the Cue API
- [ ] 4.2 Resolve the adapter via the existing registry; 400 if the
  adapter does not advertise `"csv_export"`
- [ ] 4.3 Pull the session's responses; 404 if none yet
- [ ] 4.4 Return `text/csv` with a filename of
  `responses-{platform}-{survey_id}-{timestamp}.csv` via
  `Content-Disposition: attachment`
- [ ] 4.5 Integration test that exercises the endpoint end-to-end with a
  fixture session

## 5. Cue UI

- [ ] 5.1 On the submission page, render a "Download responses as CSV"
  button alongside the existing submit button when the active platform's
  adapter advertises `"csv_export"`
- [ ] 5.2 Click handler triggers the download via the new endpoint; on
  error display the existing alert pattern
- [ ] 5.3 Template/route test asserting the button is present only when
  the capability is advertised

## 6. Docs

- [ ] 6.1 Add a short "Response export" subsection to `docs/ADAPTERS.md`
  documenting the `"csv_export"` capability, the platform import paths,
  and the column-shape contract
- [ ] 6.2 Note in `docs/OPERATOR_RUNBOOK.md` that the CSV path is a
  no-API fallback usable when LS RC2 / Qualtrics tokens are not available

## 7. Live verification

- [ ] 7.1 Extend `/tmp/limesurvey_live_verify.py` (or add a new script)
  to emit the CSV against the LS 6.17.4 docker, import it via the admin
  UI, and assert the response count
- [ ] 7.2 Manually verify the Qualtrics CSV against a sandbox account
  (skip if no sandbox available; document the gap)
