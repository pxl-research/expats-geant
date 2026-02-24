# Tasks: Implement M-Autofill Audit Logging & Compliance

## 1. Audit Trail & Data Structures

- [x] 1.1 Design audit trail schema

  - [x] 1.1a Define AuditLogEntry data structure (event type, timestamp, user_id, session_id, details)
  - [x] 1.1b Define event types (UPLOAD, SUGGEST, EDIT_SUGGESTION, SESSION_START, SESSION_END)
  - [x] 1.1c Decide storage: in-memory list per session or file-based (JSON per session)

- [x] 1.2 Create `m_shared/utils/audit.py` or `m_autofill/audit.py`
  - [x] 1.2a Define AuditLogger class with methods: log_upload(), log_suggestion(), log_edit(), log_session_event()
  - [x] 1.2b Implement thread-safe logging (session-scoped, no cross-session leaks)
  - [x] 1.2c Each audit entry includes: event_type, timestamp, session_id, details (dict with relevant data)

## 2. Integration with Existing Modules

- [x] 2.1 Integrate logging into document upload flow

  - [x] 2.1a Modify `m_autofill/ingest.py` to call AuditLogger.log_upload()
  - [x] 2.1b Capture: filename, file size, upload timestamp, session_id
  - [x] 2.1c Ensure no performance degradation from logging

- [x] 2.2 Integrate logging into suggestion generation

  - [x] 2.2a Modify `m_autofill/rag_pipeline.py` to call AuditLogger.log_suggestion()
  - [x] 2.2b Capture: question, suggested_answer, sources_used (list of source names), generation timestamp
  - [x] 2.2c Handle edge cases (LLM errors, no results)

- [x] 2.3 Integrate logging into user edits
  - [x] 2.3a Create hook for user editing suggestions (pre-implementation of 3.3)
  - [x] 2.3b Capture: original suggestion, user's edited version, edit timestamp
  - [x] 2.3c Note: API endpoint will call this in phase 3.3

## 3. Audit Report Generation

- [x] 3.1 Implement report compilation function

  - [x] 3.1a Create AuditReport class with structure: session metadata + all log entries + summary stats
  - [x] 3.1b Implement generate_audit_report(session_id) function
  - [x] 3.1c Report includes: session_id, creation_date, all uploads, all suggestions + sources, all edits, timestamps

- [x] 3.2 Implement report formatting

  - [x] 3.2a Format report as human-readable summary (Markdown or plaintext)
  - [x] 3.2b Include: Documents uploaded (count, names), Suggestions generated (count, count of user edits)
  - [x] 3.2c Include: Source citations (which documents informed which suggestions)
  - [x] 3.2d Format report for user download (can be JSON or plaintext)

- [x] 3.3 Implement report storage
  - [x] 3.3a Decide storage location: filesystem (reports/{session_id}/) or in-memory until cleanup
  - [x] 3.3b Track report metadata: generation_timestamp, retention_until (1 year from now), is_claimed

## 4. Retention Policy & Cleanup

- [x] 4.1 Implement TTL tracking

  - [x] 4.1a Each report has retention_until timestamp (session_end + 1 year)
  - [x] 4.1b Track which reports have been claimed (user download = claimed)
  - [x] 4.1c Expose remaining_time in session status (for API in phase 3.3)

- [x] 4.2 Implement retention cleanup job (initial: manual/test-only, later: scheduled)

  - [x] 4.2a Scan audit reports directory (or in-memory list)
  - [x] 4.2b Delete unclaimed reports past retention_until
  - [x] 4.2c Log cleanup actions (what was deleted, when)
  - [x] 4.2c Note: Scheduled background job deferred; manual cleanup sufficient for MVP

- [ ] 4.3 Implement Right to Be Forgotten (RTBF) support
  - [ ] 4.3a Allow explicit user request to delete audit report immediately
  - [ ] 4.3b Log deletion action for compliance
  - [ ] 4.3c Note: API endpoint in phase 3.3

## 5. Consent & Privacy Capture

- [x] 5.1 Define consent structure

  - [x] 5.1a Create Consent data model: session_id, accepted_at, terms_version, privacy_version
  - [x] 5.1b Store consent record with audit logs

- [x] 5.2 Capture consent at session creation

  - [x] 5.2a Modify SessionManager to record consent on session initialization
  - [x] 5.2b Consent is captured before any document uploads allowed

- [x] 5.3 Implement privacy/terms endpoint (static content, no logic required here)
  - [x] 5.3a Note: REST endpoint in phase 3.3
  - [x] 5.3b Define privacy statement content (data handling, retention, user rights)

## 6. Testing

- [x] 6.1 Unit tests for audit logging

  - [x] 6.1a Test AuditLogger.log_upload() with various file types and sizes
  - [x] 6.1b Test AuditLogger.log_suggestion() with multiple sources
  - [x] 6.1c Test AuditLogger.log_edit() with original vs. edited answers
  - [x] 6.1d Test thread safety (concurrent log calls in same session)

- [x] 6.2 Unit tests for report generation

  - [x] 6.2a Test generate_audit_report() with various log patterns
  - [x] 6.2b Test report includes all expected fields and metadata
  - [x] 6.2c Test formatting (plaintext, JSON, etc.)

- [x] 6.3 Unit tests for retention policy

  - [x] 6.3a Test TTL calculation (1 year from session end)
  - [x] 6.3b Test cleanup: delete unclaimed reports past TTL
  - [ ] 6.3c Test RTBF: immediate deletion on user request
  - [x] 6.3d Test edge cases (claimed reports not deleted, future reports retained)

- [x] 6.4 Unit tests for consent capture

  - [x] 6.4a Test consent recorded on session initialization
  - [x] 6.4b Test consent version tracking
  - [x] 6.4c Test edge cases (consent missing, version mismatch)

- [x] 6.5 Integration tests
  - [x] 6.5a Full session flow: initialize → upload → suggest → edit → generate report
  - [x] 6.5b Multiple documents → multiple suggestions → audit report captures all
  - [x] 6.5c Session isolation: audits from session A don't appear in session B

## 7. Manual Testing & Validation

- [ ] 7.1 Audit accuracy review

  - [ ] 7.1a Verify audit logs match actual events (uploads, suggestions, edits)
  - [ ] 7.1b Check timestamps are accurate
  - [ ] 7.1c Verify no data leakage between sessions

- [ ] 7.2 Report quality review
  - [ ] 7.2a Generate sample audit report and review for completeness
  - [ ] 7.2b Verify sources are correctly attributed in report
  - [ ] 7.2c Test retention policy manually (mark old reports, verify deletion)

## Definition of Done

- ✅ All implementation tasks complete
- ✅ All unit tests passing (minimum: 25+ tests)
- ✅ All integration tests passing
- ✅ Manual testing confirms audit accuracy and report quality
- ✅ No critical issues from code review
- ✅ Ready to hand off to 3.3 (API endpoints)
