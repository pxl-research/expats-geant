# Capability: Audit & Compliance

Session audit logging and report generation for transparency and user traceability.

## Requirements

### Requirement: Session Audit Trail

The system SHALL log all suggestion activity within a user session with complete traceability.

#### Scenario: Log document upload

- **WHEN** a document is uploaded to a session
- **THEN** an audit log entry records:
  - Event type: UPLOAD
  - Timestamp (when uploaded)
  - Session ID
  - Filename, file size, file type
  - User action (explicit upload)

#### Scenario: Log suggestion generation

- **WHEN** an answer suggestion is generated
- **THEN** an audit log entry records:
  - Event type: SUGGEST
  - Timestamp (when generated)
  - Session ID, Question ID (if available)
  - Suggested answer text (full)
  - Sources used (list of source document names and chunk indices)
  - LLM model used (for reproducibility)

#### Scenario: Log user edits

- **WHEN** a user modifies a suggestion before submission
- **THEN** an audit log entry records:
  - Event type: EDIT_SUGGESTION
  - Timestamp (when edited)
  - Session ID
  - Original suggestion (full text)
  - User's edited version (full text)
  - Change summary (optional; what user changed)

#### Scenario: Log session lifecycle events

- **WHEN** a session is created or ended
- **THEN** audit log entries record:
  - Event type: SESSION_START or SESSION_END
  - Session ID
  - Start/end timestamp
  - Reason for session end (if applicable: user logout, timeout, explicit close)

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

### Requirement: Audit Data Retention

The system SHALL store audit reports with GDPR-compliant retention policy.

#### Scenario: User downloads audit report

- **WHEN** a session completes
- **THEN** the audit report is made available for user download
- **AND** a retention clock starts: user has ~1 year to claim (download) the report
- **AND** system records timestamp of download (report is now claimed)

#### Scenario: Auto-delete unclaimed reports

- **WHEN** an audit report's retention period (~1 year) expires
- **THEN** it is automatically deleted from storage
- **AND** deletion is logged (for compliance records, separate from audit reports)
- **AND** unclaimed reports are not returned in user queries

#### Scenario: Support Right to Be Forgotten

- **WHEN** a user explicitly requests deletion of an audit report (RTBF)
- **THEN** the report is deleted immediately
- **AND** deletion is logged
- **AND** user receives confirmation of deletion

#### Scenario: Claimed reports are retained indefinitely

- **WHEN** a report is claimed (user downloads it)
- **THEN** the retention clock stops
- **AND** report is retained indefinitely (not auto-deleted)
- **AND** user can re-download at any time

### Requirement: Session Consent & Privacy Notice

The system SHALL capture user consent at session start and provide privacy transparency.

#### Scenario: Consent at session creation

- **WHEN** a session is initiated
- **THEN** user is presented with consent terms covering:
  - Data collection (documents, suggestions, edits, audit logging)
  - Retention policy (audit reports retained ~1 year unless claimed)
  - Privacy safeguards (session isolation, TTL cleanup)
  - Right to deletion (RTBF, explicit cleanup)
- **AND** user explicitly accepts before proceeding
- **AND** consent acceptance is recorded in audit log

#### Scenario: Privacy endpoint provides transparency

- **WHEN** user accesses the privacy information endpoint
- **THEN** they receive clear, plaintext information about:
  - What data is collected (documents, suggestions, audit logs)
  - How long it's retained (session TTL, audit report retention)
  - Who has access (user only; no admin access to user data)
  - User rights (download audit report, request deletion, RTBF)
  - Technical safeguards (encryption, session isolation)

#### Scenario: Privacy notice is accessible throughout session

- **WHEN** a user is in an active session
- **THEN** privacy information is available on demand (no re-consent required)
- **AND** user can download current privacy policy at any time

### Requirement: Audit Trail Accuracy & Integrity

The system SHALL maintain accurate, tamper-evident audit logs.

#### Scenario: Log entries are immutable

- **WHEN** an audit log entry is created
- **THEN** it cannot be modified or deleted (except during session cleanup)
- **AND** log order is preserved (chronological)

#### Scenario: Clock skew handling

- **WHEN** audit entries are logged
- **THEN** timestamps use server time (not client time)
- **AND** clock skew is handled gracefully (no false ordering)

#### Scenario: Audit logs survive session cleanup

- **WHEN** a session expires
- **THEN** operational data (documents, vectors) is deleted
- **AND** audit logs are preserved (compiled into final report)
- **AND** report is available for user download during retention window

## Notes

- MVP scope: Session-level audit logging (not system-wide admin logs)
- Audit report structure mirrors user experience: questions → suggestions → sources → user edits
- Retention policy: ~1 year for unclaimed reports; user can request earlier deletion
- Located in `m_shared/utils/` or `cue_api/audit.py`
- Privacy endpoint: standard EULA/privacy disclosure (separate from functionality)
