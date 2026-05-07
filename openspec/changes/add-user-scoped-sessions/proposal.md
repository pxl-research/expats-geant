# Change: Add user-scoped session management

## Why

Sessions are currently derived from the JWT token hash — each new token creates a unique,
isolated session. This makes cross-device resume impossible (same user on mobile gets a
different session than on desktop), prevents working on multiple surveys concurrently,
and blocks session handoff between users (preparer → validator workflow).

## What Changes

- **User-scoped session directories**: sessions are stored under
  `data/sessions/{user_hash}/{session_id}/` instead of `data/sessions/{token_hash}/`.
  `user_hash = sha256(user_id)[:16]`, `session_id` is a random UUID.
- **Session list endpoint**: `GET /sessions` returns all active sessions for the
  authenticated user, derived from the filesystem (no index file).
- **Session selection**: JWT `session_id` claim references the actual filesystem session.
  API token endpoint accepts an optional `session_id` to resume an existing session.
- **Session transfer**: `POST /sessions/{session_id}/transfer` moves a session from one
  user's directory to another's. Requires the recipient to have logged in at least once.
  One owner at a time (handoff, not share).
- **Cue UI session list page**: after login, users see their active sessions and can
  resume or start a new one.
- **Backward-compatible API**: `POST /auth/token` without `session_id` creates a new
  session (existing behavior). With `session_id`, it resumes.

## Impact

- Affected specs: `auth-security`, `survey-ui`
- Affected code:
  - `m_shared/session/manager.py` (user folder + nested session layout)
  - `m_shared/auth/middleware.py` (session lookup by user_hash + session_id)
  - `m_shared/auth/jwt_handler.py` (session_id claim = filesystem session_id)
  - `m_shared/auth/oauth.py` (OIDC creates user folder, generates session_id)
  - `cue_api/routes/auth.py` (optional session_id in token request)
  - `cue_api/routes/session.py` (list sessions, transfer endpoint)
  - `cue_ui/routes/` (session list page, redirect after login)
  - `cue_ui/templates/` (new session list template)
  - `run_api.py` (cleanup job scans nested structure)
- Not in scope: shared concurrent access to a session by multiple users, real-time
  collaboration, Shape UI changes
