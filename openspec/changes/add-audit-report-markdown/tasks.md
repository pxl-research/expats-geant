## 1. Backend — Markdown formatter

- [ ] 1.1 Add `_format_audit_markdown()` function in `cue_api/routes/audit.py`
- [ ] 1.2 Add `format=markdown` branch in `get_audit_report()` endpoint
- [ ] 1.3 Write unit tests for Markdown output (structure, headings, content)

## 2. Cue UI — Audit report page

- [ ] 2.1 Add `GET /audit-report` route in Cue UI that fetches Markdown from API and renders as HTML
- [ ] 2.2 Create `cue_ui/templates/audit_report.html` template
- [ ] 2.3 Add `@media print` CSS for clean print/save-as-PDF output
- [ ] 2.4 Add link to audit report page from the answer report and/or submission confirmation page

## 3. Testing

- [ ] 3.1 Smoke-test: complete a Cue session, view audit report in browser, print to PDF
- [ ] 3.2 Verify JSON and plaintext formats still work unchanged
