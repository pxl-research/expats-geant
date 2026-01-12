# Phase 2.3: Session TTL and Cleanup Implementation Tasks

## 1. Session Model Updates

- [ ] 1.1 Add `created_at: datetime` field to `m_shared/models/session.py`
- [ ] 1.2 Add `ttl_hours: int` field (default 48) to Session model
- [ ] 1.3 Add `computed_property` or method `expires_at() -> datetime` returning created_at + ttl_hours
- [ ] 1.4 Add `remaining_ttl_seconds() -> int` method for API responses
- [ ] 1.5 Unit tests for TTL calculations

## 2. Cleanup Job Implementation

- [ ] 2.1 Create `m_autofill/cleanup.py` module
- [ ] 2.2 Implement `SessionCleanupJob` class with `run()` method
- [ ] 2.3 Implement `find_expired_sessions(current_time) -> list[Session]` to identify sessions past TTL
- [ ] 2.4 Implement `cleanup_session(session_id: str)` that:
  - Deletes from vector DB collection
  - Removes temporary documents from filesystem
  - Marks session as deleted in Session model (or removes it)
- [ ] 2.5 Handle errors gracefully (log failures, continue with other sessions)
- [ ] 2.6 Unit tests for cleanup logic (mock sessions with various TTL states)

## 3. Vector DB Integration

- [ ] 3.1 Update `m_shared/vectordb/client.py` to track session creation time
- [ ] 3.2 Ensure `delete_session_collection()` completely removes all data for the session
- [ ] 3.3 Unit tests verifying data is actually deleted (cannot query after cleanup)

## 4. Document Processor Integration

- [ ] 4.1 Update `m_autofill/document_processor.py` to timestamp document uploads with session association
- [ ] 4.2 Ensure temporary files are cleaned up when session is deleted
- [ ] 4.3 Unit tests for document cleanup on session deletion

## 5. Scheduled Job Setup

- [ ] 5.1 Implement `ScheduledCleanupRunner` to periodically invoke cleanup job
- [ ] 5.2 Add environment variable: `CLEANUP_JOB_INTERVAL_MINUTES` (default 60)
- [ ] 5.3 Add async task scheduling (use APScheduler or similar lightweight scheduler)
- [ ] 5.4 Ensure cleanup job is started on application initialization

## 6. API Response Enhancement

- [ ] 6.1 Update session response to include `expires_at` timestamp
- [ ] 6.2 Update session response to include `remaining_ttl_seconds` for client visibility
- [ ] 6.3 Unit tests for API response format

## 7. Testing

- [ ] 7.1 Unit tests for TTL calculations and expiration detection
- [ ] 7.2 Unit tests for cleanup job (expired sessions removed, active sessions preserved)
- [ ] 7.3 Integration test: create session → add documents → wait until TTL → cleanup → verify data gone
- [ ] 7.4 Integration test: concurrent sessions, verify selective cleanup
- [ ] 7.5 Integration test: cleanup job error handling (one failed session doesn't block others)
- [ ] 7.6 All tests passing, 80%+ code coverage

## 8. Configuration & Monitoring

- [ ] 8.1 Update `.env.example` with new variables (SESSION_TTL_HOURS, CLEANUP_JOB_INTERVAL_MINUTES)
- [ ] 8.2 Add logging to cleanup job (sessions cleaned, errors, timing)
- [ ] 8.3 Add optional metrics: cleanup job run count, sessions deleted per run

## 9. Documentation

- [ ] 9.1 Docstrings for SessionCleanupJob and related functions
- [ ] 9.2 Brief explanation of TTL behavior in `m_autofill/` README
- [ ] 9.3 Operational documentation on configuring cleanup interval
