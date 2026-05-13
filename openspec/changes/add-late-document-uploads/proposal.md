# Change: Allow uploading documents mid-review and regenerating affected suggestions

## Why

Today a respondent uploads source documents once, then proceeds to the review page
where suggestions are streamed. If they realise mid-review that they forgot a document,
they cannot add it without abandoning their progress: the documents step lives before
the review page, the cache-filter in the UI proxy
(`cue_ui/routes/review.py:259-264`) skips any question that already has a cached
suggestion, and there is no UI affordance to ask for a refresh.

The pilot surveys at PXL/Belnet expect long, evidence-heavy questionnaires where this
case will occur regularly. We want a low-friction "add another source and refresh the
questions that could benefit" flow without throwing away the user's review work so far.

## What Changes

- **Cue API**
  - `ItemSuggestion` gains a `generated_at` ISO timestamp so cached entries carry it.
  - `GET /session/stats` adds `last_upload_at`: the timestamp of the most recent
    document or text-snippet ingestion in the session (null if none).
  - The contract that re-suggesting an item ID overwrites its cache entry (already the
    behaviour of `_cache_suggestion`) is documented as a requirement.
- **Cue UI**
  - A document-upload widget on the review page, posting to the existing
    `/session/{id}/upload-doc` and `/session/{id}/upload-text-snippet` routes.
  - A new UI-only proxy route `GET /session/{id}/regenerate-stream` that mirrors
    `/suggest-stream` minus the cache filter. The Cue API itself is unchanged.
  - A per-question **Regenerate** button inside the suggestion block, visible iff the
    cached suggestion is older than `last_upload_at`. Hides on click, reappears
    automatically the next time `last_upload_at` advances past the new `generated_at`.
  - A bulk **Regenerate untouched suggestions** button next to "Accept all",
    visible/enabled iff at least one untouched question (no `review_state`) has a
    cached suggestion older than `last_upload_at`. Opens a confirm dialog
    ("This may take a while"), then opens the regenerate SSE stream and is disabled
    until the `done` event arrives.

## Impact

- Affected specs: `answer-suggestion`, `survey-ui`
- Affected code:
  - `cue_api/models.py` — add `generated_at` to `ItemSuggestion`; add `last_upload_at`
    to `SessionStatsResponse`.
  - `cue_api/routes/suggestions.py` — populate `generated_at` on each emitted item
    (batch and stream).
  - `cue_api/routes/session.py` + `m_shared/session/manager.py` — derive
    `last_upload_at` (max `ingested_at` across session chunks, or persist on each
    upload — see `design.md`).
  - `cue_ui/routes/review.py` — new `regenerate-stream` route; review page passes the
    `last_upload_at` value to the template.
  - `cue_ui/templates/survey.html` + `partials/suggestion_block.html` — upload widget,
    per-question button, bulk button, visibility rules.
  - `cue_ui/static/review.js` + `documents.js` — wire up the buttons and the
    "disable-until-done" state machine.
- Out of scope: changes to the answer-report rendering (append-only history is kept
  intentionally — re-generations appear as additional entries with their own
  timestamps).
