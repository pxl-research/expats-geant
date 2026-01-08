# Capability: Audit & Compliance

Session audit logging and report generation for transparency and user traceability.

## ADDED Requirements

### Requirement: Session Audit Trail

The system SHALL log all suggestion activity within a user session.

#### Scenario: Log suggestion generation

- **WHEN** an answer suggestion is generated
- **THEN** an audit entry records question_id, suggested_answer, sources_used, timestamp

#### Scenario: Log user edits

- **WHEN** a user modifies a suggestion before submission
- **THEN** an audit entry records the original suggestion and user's edited version

#### Scenario: Log document uploads

- **WHEN** documents are uploaded
- **THEN** an audit entry records filename, size, upload timestamp, and session_id

### Requirement: Session Audit Report

The system SHALL generate a complete audit report at session completion or on demand.

#### Scenario: Generate audit report on session end

- **WHEN** a session is completed
- **THEN** a report is generated containing all suggestions, sources, edits, and timestamps

#### Scenario: Include answer context in report

- **WHEN** an audit report is generated
- **THEN** it includes original suggestion, user-provided answer (if edited), and source citations

#### Scenario: Report enables user traceability

- **WHEN** a user downloads an audit report
- **THEN** they can review and verify which suggestions and sources were used during the session

### Requirement: Audit Data Retention

The system SHALL store audit reports with configurable retention.

#### Scenario: User downloads audit report

- **WHEN** a session completes
- **THEN** the audit report is made available for user download

#### Scenario: Auto-delete unclaimed reports

- **WHEN** an audit report remains unclaimed after retention period (e.g., ~1 year)
- **THEN** it is automatically deleted

### Requirement: Session Consent & Privacy Notice

The system SHALL capture user consent at session start.

#### Scenario: Consent at session creation

- **WHEN** a session is initiated
- **THEN** user agrees to privacy terms and consents to audit logging

#### Scenario: Privacy endpoint provides transparency

- **WHEN** user accesses privacy endpoint
- **THEN** they receive clear information about data handling and retention

## Notes

- MVP scope: Session-level audit logging (not system-wide admin logs)
- Audit report structure mirrors user experience: questions → suggestions → sources → user edits
- Retention policy: ~1 year for unclaimed reports; user can request earlier deletion
- Located in `m_shared/utils/` or `m_autofill/audit.py`
- Privacy endpoint: standard EULA/privacy disclosure (separate from functionality)
