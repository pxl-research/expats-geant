## MODIFIED Requirements

### Requirement: Session Audit Report

The system SHALL generate a complete audit report at session completion or on demand.

#### Scenario: Generate audit report on session end

- **WHEN** a session ends
- **THEN** a complete audit report is generated containing:
  - Session metadata (session_id, creation_timestamp, end_timestamp)
  - Document uploads (count, list with names/sizes/timestamps)
  - Suggestions generated (count, list with questions/answers/sources/timestamps)
  - User edits (count, list with before/after pairs)
  - Summary statistics (total documents, total suggestions, total edits, sources per suggestion)

#### Scenario: Report includes answer context and citations

- **WHEN** an audit report is generated
- **THEN** for each suggestion it includes:
  - Original LLM suggestion
  - Sources cited (document names, chunk indices, timestamps)
  - User's edited version (if applicable)
  - Indication of which suggestion was actually used/submitted

#### Scenario: Report enables user traceability

- **WHEN** a user accesses their audit report
- **THEN** they can clearly see and verify:
  - Which documents informed each suggestion (citations)
  - How suggestions were edited or rejected
  - Timestamps for all activity
  - Reasoning (sources used for each answer)

#### Scenario: Generate report on demand

- **WHEN** a user or administrator requests an audit report for a session
- **THEN** a report is generated immediately (not just at session end)
- **AND** report reflects all activity up to the time of request

#### Scenario: Report available in multiple formats

- **WHEN** a user requests an audit report via the API
- **THEN** the report is available in JSON, plaintext, or Markdown format via the `format` query parameter
- **AND** Markdown format includes structured headings, document and suggestion lists, and summary statistics suitable for rendering as HTML or printing to PDF
- **AND** the default format remains JSON
