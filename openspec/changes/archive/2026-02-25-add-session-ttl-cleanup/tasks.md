# Phase 2.3: Session TTL and Cleanup Implementation Tasks

## 1. Session Model Updates ✅ COMPLETE

- [x] 1.1 Add `created_at: datetime` field to `m_shared/models/session.py`
- [x] 1.2 Add `ttl_hours: int` field (default 48) to Session model (stored in metadata)
- [x] 1.3 Add `expires_at: datetime` field calculated from created_at + ttl_hours
- [x] 1.4 Add `time_remaining() -> timedelta` method for API responses
- [x] 1.5 Unit tests for TTL calculations

## 2. Cleanup Job Implementation ✅ COMPLETE (Core Logic)

- [x] 2.1 `cleanup_expired_sessions()` method implemented in `m_shared/session/manager.py`
- [x] 2.2 Logic to identify and remove expired sessions
- [x] 2.3 `find_expired_sessions()` logic integrated into cleanup_expired_sessions()
- [x] 2.4 `delete_session(session_id)` implements cascading cleanup:
  - Deletes from vector DB collection
  - Removes documents from filesystem
  - Removes metadata and audit logs
- [x] 2.5 Error handling (logs failures, continues with other sessions)
- [x] 2.6 Unit tests for cleanup logic

## 3. Vector DB Integration ✅ COMPLETE

- [x] 3.1 Session creation time tracked in metadata.json
- [x] 3.2 ChromaDB collections deleted when session deleted (via path removal)
- [x] 3.3 Tests verifying data is actually deleted

## 4. Document Processor Integration ✅ COMPLETE

- [x] 4.1 Documents stored in session-scoped directories with timestamps
- [x] 4.2 Temporary files cleaned up when session is deleted (cascading delete)
- [x] 4.3 Unit tests for document cleanup on session deletion

## 5. Scheduled Job Setup ✅ COMPLETE

- [x] 5.1 Implement `ScheduledCleanupRunner` in `run_api.py` — asyncio background task that calls `cleanup_expired_sessions()` at a fixed interval
- [x] 5.2 Add `CLEANUP_JOB_INTERVAL_MINUTES` (default 60) to `.env.example`
- [x] 5.3 No additional dependency needed — used FastAPI lifespan + `asyncio.create_task` instead of APScheduler (simpler, no extra dependency, idiomatic for single-instance on-premise deployment)
- [x] 5.4 Cleanup job started/stopped via FastAPI `lifespan` context manager passed to `create_app()`

## 6. API Response Enhancement ✅ COMPLETE

- [x] 6.1 Session response includes `expires_at` timestamp
- [x] 6.2 Session response includes `remaining_hours` for client visibility
- [x] 6.3 Unit tests for API response format (in test_session_api.py)

## 7. Testing ✅ COMPLETE

- [x] 7.1 Unit tests for TTL calculations and expiration detection
- [x] 7.2 Unit tests for cleanup job (expired sessions removed, active sessions preserved)
- [x] 7.3 Integration tests for full lifecycle (create → add documents → cleanup)
- [x] 7.4 Integration tests for concurrent sessions and selective cleanup
- [x] 7.5 Error handling tested
- [x] 7.6 All existing tests passing (280+ passing)

## 8. Configuration & Monitoring ✅ COMPLETE

- [x] 8.1 `SESSION_TTL_HOURS` in `.env.example` ✓
- [x] 8.2 `CLEANUP_JOB_INTERVAL_MINUTES` added to `.env.example` under Session & Storage section
- [x] 8.3 Logging present in `SessionManager.cleanup_expired_sessions()` and `_cleanup_old_reports()`
- [x] 8.4 Implicit metrics: deleted session count returned from cleanup methods

## 9. Documentation ✅ COMPLETE

- [x] 9.1 Comprehensive docstrings present for SessionManager, delete_session, cleanup_expired_sessions
- [x] 9.2 TTL behavior documented in `m_autofill/README.md` (mentions ephemeral storage, TTL cleanup)
- [x] 9.3 `ScheduledCleanupRunner` in `run_api.py` has class docstring explaining design (sleep-first loop, asyncio task, lifespan integration) and inline comments

## SUMMARY

**What's Done:** All core cleanup logic, data models, API integration, and tests.
**What's Needed:** Background scheduler to periodically invoke `cleanup_expired_sessions()` (5 tasks, ~30-40 lines of code).
