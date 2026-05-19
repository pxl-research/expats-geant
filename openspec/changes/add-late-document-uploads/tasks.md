# Tasks

## 1. Cue API — minimal surface changes

- [ ] 1.1 Add `generated_at: str` field to `ItemSuggestion` in `cue_api/models.py`
- [ ] 1.2 Stamp `generated_at` on each emitted suggestion in
  `cue_api/routes/suggestions.py` (`_to_item_suggestion` callers in both batch and
  stream paths)
- [ ] 1.3 Add `last_upload_at: str | None` to `SessionStatsResponse` in
  `cue_api/models.py`
- [ ] 1.4 In `m_shared/session/manager.py::get_session_stats`, compute
  `last_upload_at = max(ingested_at across all chunks)` while iterating collections;
  return ISO-format string or `None`
- [ ] 1.5 Unit test: cached suggestion round-trips `generated_at`
- [ ] 1.6 Unit test: `get_session_stats` returns `last_upload_at` matching the most
  recent ingest; returns `None` for an empty session

## 2. Cue UI — mid-review upload widget

- [ ] 2.1 Add a compact upload form (file input + optional text snippet + label) to
  the "Uploaded documents" `<details>` block in
  `cue_ui/templates/survey.html`
- [ ] 2.2 Reuse existing endpoints: `POST /session/{id}/upload-doc` and
  `POST /session/{id}/upload-text-snippet`
- [ ] 2.3 Wire client-side handler in `cue_ui/static/review.js` (or a small new file)
  that, on successful upload, refreshes the document list, updates `last_upload_at`
  via `GET /session/stats`, and re-evaluates button visibility
- [ ] 2.4 Show inline success/error feedback for each upload attempt; do not navigate
  away from the review page
- [ ] 2.5 Integration test (TestClient): upload after suggestions cached succeeds and
  the cache is untouched

## 3. Cue UI — regenerate-stream proxy

- [ ] 3.1 Add `GET /session/{id}/regenerate-stream` to `cue_ui/routes/review.py`,
  copied from `/suggest-stream` but **omitting** the cached-IDs filter (the proxy
  forwards whatever IDs the client requested)
- [ ] 3.2 Accept an optional `ids` query parameter (comma-separated question IDs); if
  omitted, regenerate every question (used only by the bulk button, which passes the
  full untouched-and-stale set)
- [ ] 3.3 Reuse the existing SSE rendering for `event: suggestion` so the suggestion
  block markup is identical to the initial stream
- [ ] 3.4 Unit test: proxy posts the expected `BatchSuggestItem` list upstream

## 4. Cue UI — per-question Regenerate button

- [ ] 4.1 In `cue_ui/templates/partials/suggestion_block.html`, add a Regenerate
  button alongside Accept/Dismiss; render only when
  `cached.generated_at` is present and predates `last_upload_at`
- [ ] 4.2 Add visibility helper in `review.js`: on `last_upload_at` change or new
  suggestion event, recompute per-question button visibility
- [ ] 4.3 Click handler: disable the button, open the regenerate SSE stream with
  `ids={this_question_id}`, re-enable on matching `event: suggestion` for this id
- [ ] 4.4 Visual test: button disappears after the new suggestion arrives (because
  the new `generated_at` is now ≥ `last_upload_at`)

## 5. Cue UI — bulk Regenerate Untouched button

- [ ] 5.1 Add button in `survey.html` next to the existing "Accept all suggestions"
  control
- [ ] 5.2 Enabled iff `count_untouched_stale() ≥ 1` where untouched ⇔
  `review_state.get(q) === undefined` and stale ⇔ `cached[q].generated_at <
  last_upload_at`
- [ ] 5.3 Click opens a confirm dialog: "Regenerate N suggestions? This may take a
  while." Cancel closes without action
- [ ] 5.4 Confirm starts the SSE stream with the untouched-stale id list, disables
  the button, and re-enables on `event: done` or `event: error` or stream close
- [ ] 5.5 Integration test: bulk regenerate skips questions with `review_state` set;
  re-runs the rest; cache entries for those ids are overwritten

## 6. Documentation & validation

- [ ] 6.1 Update `docs/CUE_API.md`: note `generated_at` on `ItemSuggestion` and
  `last_upload_at` on `/session/stats`
- [ ] 6.2 Update `cue_ui/README.md` (one-paragraph note that documents can be added
  mid-review and how regeneration works)
- [ ] 6.3 Run `pytest` and confirm all suites green
- [ ] 6.4 Run `openspec validate add-late-document-uploads --strict`
- [ ] 6.5 Manual smoke test: start session, get suggestions, upload extra doc, verify
  per-question and bulk buttons behave per the spec
