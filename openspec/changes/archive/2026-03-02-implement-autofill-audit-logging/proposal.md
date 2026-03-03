# Change: Implement M-Autofill Audit Logging & Compliance

## Why

Users need transparency and traceability over how M-Autofill was used during their session. Without audit logging, there's no record of which documents were uploaded, which suggestions were generated, or how users edited suggestions. Audit reports enable users to review and verify the reasoning behind suggestions, which is critical for privacy compliance (GDPR Right to Know) and building user trust.

## What Changes

- **Session Audit Trail:** Log all session activity (document uploads, suggestion generation, user edits) with timestamps
- **Audit Report Generation:** Create complete session summaries including all suggestions, sources used, user edits, and timestamps
- **Retention Policy:** Auto-delete unclaimed audit reports after ~1 year; users can request earlier deletion
- **Consent & Privacy Capture:** Record user consent at session start; provide privacy endpoint showing data handling
- **No external changes:** Internal logging; no API endpoints in this phase (those come in 3.3)

**Breaking Changes:** None

## Impact

- **Affected specs:**

  - `specs/audit-compliance/spec.md` (requirements for audit trail, reports, retention, consent)
  - `specs/data-models/spec.md` (Session model; may need audit_log fields)

- **Affected code:**

  - `m_shared/utils/audit.py` (new; audit trail and report generation)
  - `m_shared/models/session.py` (existing; add audit fields if needed)
  - `m_autofill/audit.py` (alternative location; same role)
  - `m_autofill/ingest.py` (existing; call audit logging on document upload)
  - `m_autofill/rag_pipeline.py` (from 3.1; call audit logging on suggestion generation)

- **New dependencies:** None (all dependencies already exist)

## Timeline

- **Estimated duration:** 2–3 weeks (Mar, Week 2-3)
- **Blockers:** None; depends only on Phase 1 & 2; can start in parallel with 3.1

## Implementation Approach

1. Design audit trail data structure (what to log, when, how)
2. Implement logging functions for document uploads, suggestion generation, user edits
3. Implement audit report generation (compile logs into user-facing summary)
4. Implement retention policy (TTL tracking, auto-delete job)
5. Implement consent/privacy capture at session initialization
6. Write comprehensive unit tests
7. Manual testing: verify audit logs are accurate and complete
