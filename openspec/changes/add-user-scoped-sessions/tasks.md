## 1. Session Manager — nested layout

- [x] 1.1 Add `_hash_user_id(user_id)` and `_get_user_path(user_id)` methods
- [x] 1.2 Add `ensure_user_directory(user_id)` method
- [x] 1.3 Change `_get_session_path()` to accept optional `user_id` with scan fallback
- [x] 1.4 Change `create_session()` to use UUID session_id, create under user folder
- [x] 1.5 Change `_load_session_metadata()` to accept direct `session_path`
- [x] 1.6 Rewrite `list_sessions()` to scan nested `user_dir/session_dir` structure
- [x] 1.7 Rewrite `list_sessions_for_user()` to scan user folder directly (O(1))
- [x] 1.8 Update `cleanup_expired_sessions()` to scan nested structure, prune empty user dirs
- [x] 1.9 Update `delete_session()` to remove empty user directory after last session
- [x] 1.10 Add `delete_user_data(user_id)` for RTBF
- [x] 1.11 Update AuditLogger path resolution for nested layout
- [x] 1.12 Update Shape API `get_session_path()` for nested layout
- [x] 1.13 Write/update unit tests for all changed methods

## 2. JWT and Auth — session_id alignment

- [x] 2.1 Update `create_token()` to accept `session_id: str | None = None`
- [x] 2.2 Update OIDC `exchange_code()` to create user folder, issue JWT with `session_id=None`
- [x] 2.3 Update `POST /auth/token` to accept optional `session_id` field
- [x] 2.4 Update middleware to handle `session_id=None` (session-optional endpoints)
- [x] 2.5 Add session ownership verification in middleware
- [x] 2.6 Update auth tests for new behavior

## 3. Session API endpoints

- [x] 3.1 Add `GET /sessions` endpoint — list user's sessions
- [x] 3.2 Add `POST /sessions/new` endpoint — create session, return JWT
- [x] 3.3 Add `POST /sessions/{session_id}/select` endpoint — resume session
- [x] 3.4 Add `POST /sessions/{session_id}/transfer` endpoint — handoff
- [x] 3.5 Add Pydantic models (SessionListItem, SessionListResponse, TransferRequest)
- [x] 3.6 Register new routes in `cue_api/api.py`

## 4. Cue UI — session list page

- [x] 4.1 Create `cue_ui/templates/sessions.html` — list with resume/new buttons
- [x] 4.2 Add `GET /sessions`, `POST /sessions/new`, `POST /sessions/{id}/select` routes
- [x] 4.3 Update `GET /` to redirect to `/sessions` instead of showing upload.html
- [x] 4.4 Separate upload page as `GET /upload`
- [x] 4.5 Add `api_client.list_sessions()`, `create_new_session()`, `select_session()`
- [x] 4.6 Update UI tests for new redirect behavior

## 5. Migration

- [x] 5.1 Write `scripts/migrate_sessions_to_user_scoped.py`
- [x] 5.2 ~~Add migration instructions to `docs/DEPLOYMENT.md`~~ — skipped: no production deployments on old layout; migration script exists as safety net

## 6. Testing

- [ ] 6.1 Smoke-test: OIDC login → session list → new session → upload → review → reload on different device → same session
- [ ] 6.2 Smoke-test: create two sessions, switch between them
- [ ] 6.3 Smoke-test: transfer session from User A to User B
- [x] 6.4 Verify session cleanup handles nested layout (unit tests)
- [x] 6.5 Verify RTBF deletion removes all user data (unit tests)
