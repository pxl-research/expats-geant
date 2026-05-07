## 1. Session Manager — nested layout

- [ ] 1.1 Add `_get_user_path(user_id)` method returning `base_path / sha256(user_id)[:16]`
- [ ] 1.2 Change `create_session()` to create session dir under user folder (`user_path / session_id`), auto-create user folder if missing
- [ ] 1.3 Change `_get_session_path()` to accept `(user_id, session_id)` and return `user_path / session_id`
- [ ] 1.4 Change `get_session()` to look up session under user folder
- [ ] 1.5 Rewrite `list_sessions_for_user()` to scan the user's folder directly (no full scan)
- [ ] 1.6 Update `delete_session()` to remove empty user folder after last session deleted
- [ ] 1.7 Update `cleanup_expired_sessions()` to scan nested `*/*` structure and prune empty user folders
- [ ] 1.8 Add `delete_user_data(user_id)` for RTBF — removes entire user folder
- [ ] 1.9 Write unit tests for all changed methods

## 2. JWT and Auth — session_id alignment

- [ ] 2.1 Update `create_token()` to accept `session_id=None` (for session-list-only tokens)
- [ ] 2.2 Update OIDC `exchange_code()` to create user folder, issue JWT with `session_id=None`
- [ ] 2.3 Update `POST /auth/token` to accept optional `session_id` field — if present, verify session exists under user; if absent, create new session
- [ ] 2.4 Update middleware to handle `session_id=None` (allow access to session list endpoints only)
- [ ] 2.5 Write unit tests for token creation with/without session_id, middleware session-less access

## 3. Session API endpoints

- [ ] 3.1 Add `GET /sessions` endpoint — list user's sessions (id, label, created_at, last_accessed, status, question_count)
- [ ] 3.2 Add `POST /sessions/{session_id}/select` endpoint — issues new JWT scoped to that session
- [ ] 3.3 Add `POST /sessions/{session_id}/transfer` endpoint — move session to recipient's folder, update metadata
- [ ] 3.4 Register new routes in `cue_api/api.py`
- [ ] 3.5 Write unit tests for list, select, and transfer endpoints

## 4. Cue UI — session list page

- [ ] 4.1 Create `cue_ui/templates/sessions.html` — list of sessions with resume/delete buttons
- [ ] 4.2 Add `GET /sessions` route in `cue_ui/routes/` — fetch sessions from API, render list
- [ ] 4.3 Update post-login redirect to go to session list instead of directly to upload/review
- [ ] 4.4 Add "New session" flow — create session via API, redirect to upload page
- [ ] 4.5 Add `api_client.list_sessions()` and `api_client.select_session()` functions
- [ ] 4.6 Update session cleanup to only delete the current session (not all user data)

## 5. Migration

- [ ] 5.1 Write `scripts/migrate_sessions.py` — reads flat `data/sessions/*/metadata.json`, moves each to `data/sessions/{user_hash}/{session_id}/`
- [ ] 5.2 Add migration instructions to `docs/DEPLOYMENT.md`

## 6. Testing

- [ ] 6.1 Smoke-test: OIDC login → session list → new session → upload → review → reload on different device → same session
- [ ] 6.2 Smoke-test: create two sessions, switch between them
- [ ] 6.3 Smoke-test: transfer session from User A to User B
- [ ] 6.4 Verify session cleanup handles nested layout
- [ ] 6.5 Verify RTBF deletion removes all user data
