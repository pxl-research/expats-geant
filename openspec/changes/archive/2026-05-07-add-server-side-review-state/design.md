## Context

Cue respondents review AI-generated suggestions question by question: accepting,
editing, or dismissing each one. This review state is currently stored exclusively in
the browser's localStorage via `ReviewState` (cue_ui/static/review-state.js). The
state is lost when the browser cache is cleared, and cannot be accessed from another
device or by another user.

Suggestions themselves are generated on-the-fly via the RAG pipeline (vector search +
LLM call) and logged to `answer_report.json` as an append-only JSONL file. The answer
report captures what was suggested but not what the user decided.

## Goals / Non-Goals

**Goals:**
- Review state persisted server-side in the session directory
- State survives browser cache clears and device switches
- Answer report includes review decisions (accepted/edited/dismissed + final value)
- Foundation for future session transfer between users
- Pilot KPI metrics (acceptance rate, edit rate) computable server-side

**Non-Goals:**
- Session transfer or ownership reassignment (separate future proposal)
- Real-time collaborative review (multi-user editing the same session simultaneously)
- Removing localStorage entirely (kept as optimistic cache for instant UI feedback)
- Changing how suggestions are generated (RAG pipeline unchanged)

## Decisions

### Single JSON file, not JSONL

**Decision:** Store review state as a single `review_state.json` file (full state map),
not an append-only JSONL log.

**Rationale:** Review state is mutable — a user can accept, then edit, then dismiss the
same question. A JSONL event log would require replaying history to derive current state.
A single JSON file with the latest state per question is simpler to read, write, and
serve. The file is small (one entry per survey question, typically <100 questions).

### Write per interaction, not batch on submit

**Decision:** Write review state to the API on each accept/dismiss/edit action, not
as a batch on form submission.

**Rationale:** Users may close the tab mid-review, and the "submit" action may not
exist (display-only mode). Per-interaction writes match the current localStorage
behaviour and ensure no state is lost. The cost is one small API call per interaction,
which HTMX handles naturally.

### localStorage kept as optimistic cache

**Decision:** The UI continues writing to localStorage alongside the API call. On page
load, server state takes precedence.

**Rationale:** localStorage provides instant UI feedback without waiting for the API
round-trip. If the API call fails transiently, the user's review progress is not lost
in the browser. On reload, the server state is the source of truth — the UI merges it
with any localStorage state that may have been written after the last successful API
sync.

### Answer report enrichment, not a separate download

**Decision:** Include review state inline in the answer report download, not as a
separate endpoint or file.

**Rationale:** The answer report already serves as the respondent's evidence trail.
Adding the user's decision (accepted/edited/dismissed) and final answer value per
question makes it a complete record without requiring consumers to join two files.

### API endpoint granularity

**Decision:** `PUT /review-state/{question_id}` for saving a single question's state;
`GET /review-state` for loading the full map.

**Alternatives considered:**
- *PUT /review-state (full map)*: Simpler API, but risks overwriting concurrent changes
  and sends the entire state on every interaction.
- *PATCH /review-state*: Semantically correct but adds complexity for no practical gain
  in a single-user-per-session context.

**Rationale:** Per-question PUT is the natural granularity — one interaction, one write.
The full GET is needed for page load. No batch write endpoint is needed.

## Risks / Trade-offs

- **Extra API calls**: One PUT per accept/dismiss/edit adds ~1 request per user
  interaction. At survey scale (<100 questions), this is negligible. The request body
  is tiny (question ID + state + optional value).

- **Conflict with localStorage**: If the API write fails but localStorage succeeds,
  the two stores diverge. On reload, server state wins. Mitigation: the UI can retry
  failed API writes silently; for the PoC, losing a single review action to a transient
  error is acceptable.

- **File I/O on every interaction**: Writing `review_state.json` on every action is
  fine for PoC scale. If this becomes a bottleneck at scale, the file can be replaced
  with a database row. The API contract stays the same.

## Open Questions

- Should the answer report include review state for questions where the user took no
  action (state = pending)? Proposal: omit pending questions from the review state
  section to keep the report concise.
