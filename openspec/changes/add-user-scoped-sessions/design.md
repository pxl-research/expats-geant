## Context

The current session model derives a filesystem session ID from `sha256(jwt_token)[:16]`.
This creates a 1:1 coupling between JWT and session — same user on a different device
gets a different token and therefore a different session. Users cannot resume work across
devices, cannot work on multiple surveys concurrently, and cannot hand off a session to
another user.

## Goals / Non-Goals

**Goals:**
- Same user, different device → sees and can resume their sessions
- Multiple concurrent sessions per user (one per survey)
- Session handoff from one user to another (preparer → validator)
- RTBF compliance via `rm -rf data/sessions/{user_hash}/`
- Backward-compatible API for existing server-to-server callers

**Non-Goals:**
- Shared concurrent access (two users editing the same session simultaneously)
- Real-time collaboration or conflict resolution
- Session index file or database (filesystem is the source of truth)
- Shape UI session management (Cue only for now)

## Decisions

### Filesystem layout

```
data/sessions/
  {user_hash}/                    ← sha256(user_id)[:16]
    {session_id}/                 ← uuid4().hex[:12]
      metadata.json
      survey.json
      answer_report.json
      review_state.json
      cached_suggestions.json
      audit_log.json
      chroma_{uuid}/
      uploads/
```

**Rationale:** grouping sessions under a user directory makes RTBF deletion trivial
(`shutil.rmtree(user_path)`), makes listing a user's sessions a single directory scan,
and makes ownership unambiguous from the path alone.

### No index file

Session listing is derived from `user_path.iterdir()` + reading each
`metadata.json`. For the expected scale (<100 sessions per user, <1000 users per
deployment), this is fast enough. Adding an index file creates a sync problem
(index vs filesystem can diverge) for no practical benefit at this scale.

### JWT session_id = filesystem session_id

The JWT `session_id` claim becomes the actual UUID used for the filesystem directory
name (today this claim is random and unused for filesystem lookup — the middleware
hashes the full token instead). This makes session selection explicit: the token
carries which session the user is working in.

### Session creation flow

**OIDC login (browser):**
1. User authenticates via Keycloak
2. `exchange_code()` resolves `user_id` from OIDC claims
3. User folder `data/sessions/{user_hash}/` is created if it doesn't exist
4. A new session is NOT auto-created — the JWT is issued with `session_id=None`
5. User is redirected to the session list page
6. User picks an existing session or starts a new one
7. A new JWT is issued (or the session_id is selected) for the chosen session

**API token (`POST /auth/token`):**
- Without `session_id`: creates a new session under the user's folder, returns JWT
  with the new session_id. This preserves existing behavior.
- With `session_id`: validates the session exists and belongs to the user, returns
  JWT scoped to that session.

### Session transfer (handoff)

`POST /sessions/{session_id}/transfer` with body `{"recipient_user_id": "..."}`:
1. Verify the session belongs to the caller
2. Compute `recipient_hash = sha256(recipient_user_id)[:16]`
3. Verify the recipient's user folder exists (they must have logged in at least once)
4. Move the session directory from caller's folder to recipient's folder
5. Update `metadata.json` with new `user_id`
6. Caller's JWT is no longer valid for this session

**Rationale for move (not share):** one owner at a time avoids concurrent access
complexity, makes ownership unambiguous, and matches the real-world handoff workflow
(preparer finishes, validator takes over).

### Middleware changes

Current: `session_id = claims["session_id"]` → `get_session(session_id)` (flat lookup).

New: `user_id = claims["user_id"]` → `user_hash = sha256(user_id)[:16]` →
`session_path = base_path / user_hash / session_id`. The middleware checks that the
session exists under the user's folder (enforces ownership by path structure).

### Cleanup job

Currently scans `data/sessions/*/metadata.json`. Changes to scan
`data/sessions/*/*/metadata.json` (one extra nesting level). Empty user folders
(all sessions expired) are removed.

## Risks / Trade-offs

- **Migration**: existing flat sessions need a one-time migration to the nested layout.
  A migration script moves each `data/sessions/{hash}/` into
  `data/sessions/{user_hash}/{session_id}/` based on the `user_id` in `metadata.json`.
  Can run offline before the upgrade.

- **Filesystem scanning**: listing sessions scans the directory. At PoC scale this is
  negligible. If the deployment grows to thousands of concurrent users, a database-backed
  session index would be needed — but that's well beyond current requirements.

- **Transfer recipient must exist**: if User B hasn't logged in yet, User A cannot
  transfer to them. This is a deliberate simplification — supporting deferred transfers
  adds a pending-invitation system that isn't worth the complexity for the PoC.

## Open Questions

None — all design decisions have been made in discussion.
