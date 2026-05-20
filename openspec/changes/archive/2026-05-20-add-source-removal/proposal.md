# Change: Allow respondents to remove a source from a session

## Why

After a respondent adds files, web URLs, or pasted snippets to their session,
the only way to "undo" a source today is to start a new session. That is too
heavy when:

- The user accidentally pasted the wrong URL or uploaded the wrong file.
- An intermediate document turned out to be off-topic and now distracts the
  retriever.
- A previewed-and-ingested web page contains content the user does not want
  to leave in the session's audit-discoverable evidence base.

The underlying primitive already exists: `ChromaDocumentStore.remove_document`
deletes a collection by name and is already used by the web re-ingest
overwrite path. What is missing is an authenticated API endpoint, a UI
affordance to invoke it, and an audit event so the action is recorded
alongside the original ingest.

This is a session-scoped, user-driven action — distinct from the GDPR
"delete everything for this user" capability — and it deserves its own
small surface rather than being overloaded onto the existing GDPR delete
path.

## What Changes

- **Cue API**
  - New `DELETE /session/documents/{name}` endpoint: removes the named source
    collection from the session vector store, emits a `SOURCE_REMOVED` audit
    event, and returns 200 with `{"status": "ok", "name": <name>}` on
    success, 404 when the name is not found.
  - New `SOURCE_REMOVED` audit event type recording `name`, `source_kind`
    (when known), and `source_mime` (when known) so audit consumers can see
    not just that a source was removed but what kind it was.
- **Cue UI**
  - A small remove (✕) button on every row in the sources list, on both the
    documents page and inside the mid-review widget.
  - Browser-native `confirm("Remove «name»?")` guard before the DELETE
    request fires. No modal infrastructure, no toast.
  - After a successful DELETE, the list refreshes via the existing
    `window.refreshSessionStats()` plumbing.
- **Cached suggestions are left alone by design.** A suggestion that already
  cites a removed source keeps its citation as it was generated; the user
  can use the existing per-question Regenerate button or the bulk
  "Regenerate untouched" button if they want suggestions recomputed against
  the trimmed source set. The design.md captures the rationale.
- **Documentation**
  - `docs/CUE_API.md`: document the new endpoint, its 200/404 shape, and
    the new audit event type.
  - No README changes — the button is self-explanatory.

## Impact

- Affected specs: `document-ingestion`, `survey-ui`
- Affected code:
  - `cue_api/routes/session.py` — new DELETE endpoint (lives next to the
    other single-session helpers).
  - `cue_api/models.py` — new `RemoveSourceResponse` model.
  - `m_shared/utils/audit.py` — new `SOURCE_REMOVED` event type and
    `log_source_removed(...)` helper mirroring `log_upload` / `log_web_fetch`.
  - `cue_ui/api_client.py` — new `remove_document(token, name) -> dict`.
  - `cue_ui/routes/review.py` — new DELETE proxy
    `DELETE /session/{session_id}/documents/{name}`.
  - `cue_ui/static/review.js` and `cue_ui/static/documents.js` — remove
    button per row, click handler, confirm guard, refresh on success.
  - `cue_ui/templates/documents.html` and `cue_ui/templates/survey.html` —
    server-side initial render gains the ✕ button per row to match the JS
    re-render.
  - `tests/test_session_api.py` (or a new `tests/test_source_removal.py` —
    decide during implementation based on file size) — happy path, 404 on
    unknown name, audit emission, auth gating.
  - `tests/test_ui_documents.py` / `tests/test_ui_routes.py` — proxy
    forwards request, propagates status codes.
  - `docs/CUE_API.md` — endpoint reference and audit event.
- Out of scope:
  - "Soft delete" / undo — removal is final within the session.
  - Cascade re-suggest — cached suggestions are left alone (see design.md).
  - Bulk remove (multi-select). Per-row is enough for the pilot.
  - Removing individual chunks within a source (no use case; source-level
    granularity matches every other operation).
  - Re-adding a removed source automatically. The user can paste/upload again
    if they want it back.
- Sequencing: independent. Only depends on `add-late-document-uploads` (already
  shipped) for the mid-review widget that hosts the second remove-button
  surface.
