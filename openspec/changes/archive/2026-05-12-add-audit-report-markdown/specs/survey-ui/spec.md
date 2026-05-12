## ADDED Requirements

### Requirement: Audit Report Page

The UI SHALL provide a page that renders the session audit report as styled HTML,
fetched from the Cue API in Markdown format and converted to HTML for display.
The page SHALL include print-optimized CSS so users can save or print the report
as a PDF via the browser's native print dialog.

#### Scenario: View audit report in browser

- **WHEN** the user navigates to the audit report page
- **THEN** the UI fetches the audit report as Markdown from the API
- **AND** renders it as styled HTML with structured headings, lists, and summary statistics

#### Scenario: Print or save audit report as PDF

- **WHEN** the user triggers the browser print dialog on the audit report page
- **THEN** the printed output excludes UI navigation and chrome
- **AND** uses print-friendly styling (margins, page breaks, readable font sizes)

#### Scenario: Link to audit report from existing pages

- **WHEN** the user is on the answer report page or submission confirmation page
- **THEN** a link to the audit report page is visible
