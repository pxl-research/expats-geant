# Change: Add Markdown format for audit reports

## Why

The audit report is currently available as JSON or flat plaintext. Neither format is
user-friendly for on-screen reading or printing. Adding Markdown as a format option
lets the Cue UI render the report as styled HTML and gives users a clean print-to-PDF
path via the browser's native print dialog — no server-side PDF dependency needed.

## What Changes

- Add `format=markdown` option to `GET /audit-report` endpoint (returns Markdown string)
- Add a Markdown formatter in the audit route module alongside the existing plaintext one
- Add an audit report page in Cue UI that fetches the Markdown, renders it as HTML, and
  provides a print-friendly view with `@media print` CSS
- Existing `json` and `plaintext` formats remain unchanged

## Impact

- Affected specs: `audit-compliance` (new format option), `survey-ui` (new UI page)
- Affected code: `cue_api/routes/audit.py`, `cue_ui/` (new template + route)
- No breaking changes
