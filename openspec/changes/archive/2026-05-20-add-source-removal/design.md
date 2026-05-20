# Design: Source Removal

## Goals

- Give respondents a one-click way to remove a source they no longer want in
  their session, without leaving the page or losing review state.
- Record removals in the audit log so the action is reconstructable later.
- Keep the surface area small: one endpoint, one button per row, no new
  infrastructure (no modal lib, no toast lib, no soft-delete table).

## Non-Goals

- Cross-session bulk operations (the GDPR full-wipe path already covers
  that).
- Undo / soft delete / restore. Removal is final within the session.
- Cascade re-running of suggestions when a cited source is removed
  (see Decision 1).
- Operator-side allow/blocklist of which sources can be removed.

## Decisions

### Decision 1 — Leave cached suggestions alone after a source is removed

**Decision:** When a source is removed, no cached suggestion is invalidated
or regenerated. Suggestions that already cite the removed source keep their
citation footer as it was generated.

**Why:** Suggestions are part of the user's review state. Silently rewriting
a citation footer behind the user's back risks confusion ("where did this
text come from?"); silently re-running suggestions can wipe out an
edit-in-progress or a deliberate dismiss. The existing per-question
Regenerate button and the bulk "Regenerate untouched" button already cover
the legitimate "I changed sources, refresh my suggestions" use case — and
crucially they do so under explicit user control.

**Tradeoff:** A respondent who removes a source and then submits without
regenerating may submit answers whose citations point at a source the
session no longer contains. We accept this: the audit trail will show
both the original ingest and the later `SOURCE_REMOVED` event, so an
auditor can reconstruct what happened. The citation footer remains
truthful about *what was in the session at suggestion-generation time*.

### Decision 2 — `confirm()` is sufficient guard; no custom modal

**Decision:** The remove button fires `window.confirm("Remove «name»?")`.
Cancel → nothing happens. OK → the DELETE request fires.

**Why:** The action is destructive but session-scoped and reversible by
re-adding the source. A native `confirm()` is accessible by default,
keyboard-friendly, and adds no JS dependency. A custom modal would
duplicate the existing "are you sure you want to clear this session"
pattern without adding clarity.

**Tradeoff:** Power users on auto-confirm-suppressing browser profiles
could miss the guard. We accept this — the destruction is contained to
their own session and recoverable by re-uploading.

### Decision 3 — Source-level, not chunk-level

**Decision:** Removal operates on whole sources (collections), never on
individual chunks.

**Why:** Chunk granularity has no use case — respondents identify content
by source, not by chunk index. Every other ingestion operation (upload,
overwrite, re-ingest, audit) treats the source as the atomic unit. Keeping
removal at the same granularity preserves the mental model.

### Decision 4 — `DELETE /session/documents/{name}` rather than a body
parameter

**Decision:** The endpoint takes the source name in the URL path, not in
a JSON body.

**Why:** REST orthodoxy: the document is the resource. Path-based DELETE
also composes naturally with the existing single-session route style in
`cue_api/routes/session.py` (other endpoints under `/session/...`).

**Encoding note:** Source names can contain non-URL-safe characters (the
collection name is sanitised, but the *display* name passed from the UI
is not). The UI is responsible for `encodeURIComponent`-ing the name
before constructing the URL; the API resolves the path parameter and
re-sanitises through the same `clean_up_string` / `sanitize_filename`
helper used at ingest time to find the matching collection. 404 is
returned if no collection matches.

### Decision 5 — New `SOURCE_REMOVED` audit event, not reused `UPLOAD`
inverse

**Decision:** Add a dedicated `SOURCE_REMOVED` audit event type rather
than re-emitting an `UPLOAD` event with a "deleted=true" flag or similar.

**Why:** Each audit event type today is a discrete user action; reading
the log is easier when "added a source" and "removed a source" are
visibly distinct event types. Filters and downstream consumers (the
existing audit report) don't need to learn a new convention.

**Fields:** `name` (the source as displayed to the user), `source_kind`
(file/web/text/null), `source_mime` (the MIME type or null). The new
provenance fields are populated when known; both are tolerant of the
legacy `None` case for sources ingested before the kind/mime change.

### Decision 6 — No "are you sure?" toast or undo button after deletion

**Decision:** After the DELETE returns 200, the row simply disappears and
the docs count decrements. No success toast, no undo affordance.

**Why:** Toasts add a JS dependency and clutter. The visual change (row
gone, count decremented) is itself the confirmation. Undo would require
either a server-side trash (out of scope) or a client-side replay of the
ingest (which would fail for files no longer in the browser and would
require re-fetching for URLs).

## Open Questions

- **Empty-session edge case:** What if a respondent removes every source
  and clicks Continue? The current page already supports "Continue without
  any sources" (the documents page has copy for this), and suggestions
  simply degrade to LLM-only without retrieval. No special handling is
  needed.
- **Race against an in-flight upload:** If the user clicks ✕ on a source
  while another card is mid-ingest, the in-flight counter from
  `documents.js` already disables the Continue button but not the ✕
  buttons. We accept this; the DELETE is independent of the in-flight
  ingest and the worst case is "the user removed source A while source B
  was still being added", which is fine.

## Risks

- **Risk:** A respondent removes a source and submits answers that still
  cite it. **Mitigation:** Audit trail records both events; citation
  footers describe what the session contained when the suggestion was
  generated; the existing Regenerate button offers a refresh path.
- **Risk:** Sanitisation mismatch — UI sends a name that does not resolve
  to a collection on the API side. **Mitigation:** API re-runs the same
  sanitisation used at ingest; on miss returns 404 and the UI surfaces an
  inline error.
- **Risk:** Concurrent DELETE of the same name from two tabs.
  **Mitigation:** Idempotent — second request returns 404; UI treats 404
  as "already gone" and just refreshes the list.
