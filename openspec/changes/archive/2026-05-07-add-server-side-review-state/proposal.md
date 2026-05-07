# Change: Add server-side review state persistence

## Why

A test user presented a real use case: one person uploads documents and reviews Cue
suggestions (the "preparer"), then hands the session to a second person for validation
and final submission. This is currently impossible because:

1. Review state (accepted/dismissed/edited) lives only in the browser's localStorage
2. Sessions are bound to a single user's JWT
3. Suggestions are generated on-the-fly and not cached

Moving review state to the API also solves secondary problems: resuming a session on
a different device or browser, surviving cache clears, and providing the server with
accurate acceptance/edit metrics for the audit trail and pilot KPIs.

## What Changes

- **Server-side review state**: new `review_state.json` file in the session directory,
  written via a new API endpoint. Stores per-question state (accepted/dismissed/edited)
  and the user's actual answer value.
- **API endpoints**: `PUT /review-state/{question_id}` to save a single question's
  review state, `GET /review-state` to load the full state map. Both scoped to the
  session from the JWT.
- **Cue UI adaptation**: the UI writes review state to the API (via HTMX) in addition
  to localStorage. On page load, server state takes precedence over localStorage. The
  localStorage layer is kept as a fast optimistic cache.
- **Answer report enrichment**: the answer report download includes review state
  alongside each suggestion (what the user decided and their final answer value).
- **Session transfer** (future-ready): the review state is decoupled from the original
  user's JWT. A future "transfer session" feature can reassign ownership, and the new
  user inherits the full review state. This proposal does NOT implement transfer itself.

## Impact

- Affected specs: `survey-ui`, `answer-report`, `answer-suggestion`
- Affected code:
  - `cue_api/routes/review_state.py` (new — API endpoints)
  - `cue_api/models.py` (new request/response models)
  - `cue_ui/static/review-state.js` (dual-write: API + localStorage)
  - `cue_ui/routes/review.py` (load server state on page render)
  - `cue_api/routes/suggestions.py` (enrich answer report with review state)
  - `m_shared/session/manager.py` (no changes — review_state.json is auto-cleaned
    by existing session deletion)
- Not in scope: session transfer between users (separate future proposal), Shape UI
  (Shape does not have review state)
