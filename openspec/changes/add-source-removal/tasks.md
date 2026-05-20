# Tasks

## 1. Audit event

- [ ] 1.1 Add `SOURCE_REMOVED` to `AuditEventType` in
  `m_shared/utils/audit.py`
- [ ] 1.2 Add `log_source_removed(session_id, *, name, source_kind,
  source_mime, user_id=None)` on `AuditLogger`, mirroring the shape of
  `log_upload` and `log_web_fetch`

## 2. Cue API — remove endpoint

- [ ] 2.1 Add `DELETE /session/documents/{name}` in
  `cue_api/routes/session.py`
- [ ] 2.2 Resolve the path parameter through the same
  `sanitize_filename` / `clean_up_string` helper used at ingest time
- [ ] 2.3 Look up the existing collection to capture `source_kind` and
  `source_mime` from the first chunk's metadata *before* deletion (so the
  audit event can record them)
- [ ] 2.4 Call `store.remove_document(name)`; return 200 with
  `{"status": "ok", "name": <name>}` on success
- [ ] 2.5 Return 404 with a clear message when no matching collection
  exists (idempotent for concurrent deletes)
- [ ] 2.6 Emit a `SOURCE_REMOVED` audit event on success only
- [ ] 2.7 Add a `RemoveSourceResponse` Pydantic model in
  `cue_api/models.py`
- [ ] 2.8 Integration tests: happy path removes the collection and emits
  one audit event; 404 on unknown name; 401 without a JWT;
  cross-session isolation (removing from session A does not touch session B)

## 3. Cue UI — proxy + button

- [ ] 3.1 Add `remove_document(token, name) -> dict` to
  `cue_ui/api_client.py` following the existing `_raise_for_status`
  pattern
- [ ] 3.2 Add `DELETE /session/{session_id}/documents/{name}` proxy in
  `cue_ui/routes/review.py`, forwarding the upstream status code and
  body verbatim
- [ ] 3.3 Add a ✕ button per row in `renderDocsList`
  (`cue_ui/static/review.js`) and `renderDocs`
  (`cue_ui/static/documents.js`)
- [ ] 3.4 Wire a click handler that runs `confirm("Remove «name»?")`,
  then `encodeURIComponent`s the name and sends DELETE; on success calls
  `window.refreshSessionStats()`; on failure renders an inline error
  near the row
- [ ] 3.5 Update the server-side initial render in
  `cue_ui/templates/documents.html` and `cue_ui/templates/survey.html`
  to include the same ✕ button per row so the layout matches before JS
  hydrates
- [ ] 3.6 UI tests: proxy forwards body and status; missing JWT cookie
  → 401; server-rendered row includes the button

## 4. Documentation

- [ ] 4.1 Update `docs/CUE_API.md` with `DELETE /session/documents/{name}`,
  the `SOURCE_REMOVED` audit event, and the documented decision that
  cached suggestions are intentionally not invalidated by a remove
- [ ] 4.2 Confirm `cue_ui/README.md` still reads correctly with the new
  button mentioned in the documents-page paragraph; one-line addition
  only if it is not implicit already

## 5. Validation

- [ ] 5.1 `pytest` — full suite green
- [ ] 5.2 `openspec validate add-source-removal --strict`
- [ ] 5.3 Manual smoke: upload a file, paste text, ingest a URL; remove
  each in turn; verify the docs list updates, the docs count
  decrements, and `GET /audit-report` shows three `SOURCE_REMOVED`
  entries with correct `source_kind` values
- [ ] 5.4 Manual smoke: regenerate a suggestion before and after a
  remove to confirm the existing Regenerate path still works against
  the trimmed source set
- [ ] 5.5 Manual smoke: open the same session in two tabs, remove the
  same source from both; second tab's DELETE returns 404 and the UI
  recovers gracefully (refresh shows the source is gone)
