# Design: Late document uploads and suggestion regeneration

## Context

The existing flow assumes a respondent uploads all documents up front, then reviews
suggestions in a single linear pass:

- `cue_ui/routes/review.py:25` — `/session/{id}/documents` page (upload step).
- `cue_ui/routes/review.py:149` — `/session/{id}/review` page (loads survey + cached
  suggestions + review state).
- `cue_ui/routes/review.py:244` — `/session/{id}/suggest-stream` SSE proxy. **Filters
  out any question that already has a cached suggestion** (lines 259-264).
- `cue_api/routes/suggestions.py:199` — `POST /suggest/stream` accepts any item list,
  emits one SSE event per item, and upserts each into
  `cached_suggestions.json` via `_cache_suggestion` (line 64).
- `cue_api/routes/documents.py:22` — `/upload` already works at any time; no "first
  time only" guard.

Pilot users have asked: "I forgot a document, can I add it and refresh the questions I
haven't looked at yet?" Today the answer is "no" without restarting.

## Goals / Non-Goals

**Goals**
- Let respondents add documents and text snippets after suggestions have started
  streaming, without losing their review state (`accepted`/`dismissed`/edits) or their
  in-progress form input.
- Provide a per-question Regenerate button that appears exactly when it could
  meaningfully help — i.e. when a new document has been added since this suggestion
  was generated.
- Provide a bulk Regenerate Untouched button so users with long surveys don't have to
  click each question.
- Keep the audit trail truthful: regenerations append new entries to
  `answer_report.json` rather than overwriting prior ones.

**Non-Goals**
- No re-ranking, no quality scoring of new vs old suggestions.
- No undo for regeneration (the previous cached suggestion is overwritten on purpose
  — the audit log preserves it).
- No new Cue API endpoint. The existing `/suggest/stream` already supports the use
  case once we route around the UI-side cache filter.

## Decisions

### Decision 1: No new Cue API endpoint for regeneration

`POST /suggest/stream` already accepts any item list and `_cache_suggestion` is an
upsert. The only thing blocking reuse is the UI proxy's cache-skip filter at
`cue_ui/routes/review.py:259-264`. We add a sibling UI route
`/session/{id}/regenerate-stream` identical to `/suggest-stream` but without the
cache filter. Both routes forward to the same `POST /suggest/stream` upstream.

*Alternative considered:* Add a `force=true` query param on the existing
`/suggest-stream` proxy. Rejected because the two flows have meaningfully different
UX (initial load vs explicit refresh), and a flag-driven branch in one route is
harder to read than two thin routes.

### Decision 2: `generated_at` on `ItemSuggestion`, not a sidecar

The staleness rule per question is `cached.generated_at < last_upload_at`. The cache
file (`cached_suggestions.json`) stores `ItemSuggestion.model_dump()`. We add
`generated_at: str` directly to `ItemSuggestion`. Batch and stream endpoints both
already compute a timestamp; they just stamp it into the item now instead of (or as
well as) the response wrapper.

*Alternative considered:* Track `(item_id → timestamp)` in a separate cache sidecar.
Rejected as redundant state. The cache *is* the per-item record.

*Backwards compatibility:* Existing per-session caches predate this field. Sessions
are ephemeral (24–48h TTL), so no migration is needed. The UI treats a missing
`generated_at` as "no timestamp known → never show regenerate button" — safer than
"always show," which could surprise users with buttons on suggestions that don't
actually need refresh.

### Decision 3: `last_upload_at` derived in `SessionManager`, not stored

Each chunk already stamps `ingested_at` in its ChromaDB metadata
(`cue_api/ingest.py:84,154`). `get_session_stats` walks the session's collections
already (to count chunks). It can compute `max(ingested_at)` in the same pass, no
new field needed.

*Alternative considered:* Persist `last_upload_at` in session metadata, bumped on
each upload. Rejected because it introduces a second source of truth that can drift
(e.g. if a chunk is added but the metadata write fails).

*Trade-off:* Slightly more work per stats call (one metadata fetch per collection).
Acceptable: stats is called once on review page load and possibly on each upload
completion, not on every keystroke.

### Decision 4: Bulk button targets "untouched" only

"Untouched" means the question has no entry in `review_state.json` (i.e. not
accepted, not dismissed, not explicitly edited). This deliberately ignores form-input
typing that hasn't been "Accepted." Users who typed something but didn't accept it
will see it overwritten if they click bulk Regenerate, but they did opt in by clicking
a labelled button on a confirm dialog. Per-question Regenerate is the surgical
alternative.

Both buttons share one staleness predicate:

```
is_stale(q) = cached[q].generated_at < last_upload_at
```

The bulk button additionally requires `review_state.get(q) is None`.

### Decision 5: Disable-during-stream scope

- Per-question Regenerate: button disables on click and re-enables when that
  question's `suggestion` event arrives (matched by `item_id`). Multiple buttons can
  be fired in parallel; each clears itself.
- Bulk Regenerate: button disables on click and re-enables when the SSE `done` event
  is received, the stream closes, or an `error` event is received. Prevents stacking
  parallel streams over the same session.

### Decision 6: Audit log keeps regenerations

`_append_to_answer_report` already appends to JSONL. We keep that behaviour. A
question regenerated three times will have three entries with three timestamps —
truthful audit trail. The answer-report rendering already shows entries chronologically
and is not in scope of this change.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| User clicks bulk Regenerate during an in-flight initial suggestion stream | Bulk button disabled until *all* questions either have a cached suggestion or have failed (visibility rule depends on `cached.generated_at`, which doesn't exist until the first stream completes) |
| `last_upload_at` query reads all collections — slow on large sessions | Sessions are bounded by file-size + chunk caps already; review-page load already lists collections. No new N+1 introduced. |
| Old cached entries (pre-change) have no `generated_at` | UI treats missing field as "never stale" — button never shows, no false positives. |
| User uploads document while bulk regenerate is mid-stream | `last_upload_at` advances; some items in the in-flight stream will be regenerated against the older corpus snapshot. Acceptable: the next regenerate cycle will catch up; the audit log records both. |
| Answer report grows duplicate entries | Out of scope. Acceptable for PoC; review-page rendering tolerates duplicates today. Revisit if pilot feedback flags it. |

## Migration Plan

None required. Server-side changes are additive (new field, new derived field, new UI
route). Existing caches without `generated_at` simply never trigger a Regenerate
button, which is the desired safe default. As sessions expire (24–48h TTL), they roll
over to the new format naturally.

## Open Questions

- Should the bulk button's confirm dialog state the number of questions that will be
  regenerated? (Probably yes — useful information, not implementation leakage.)
  Resolved in tasks: dialog says "Regenerate N suggestions? This may take a while."
- Should we expose `last_upload_at` to the UI via a small JSON endpoint instead of
  templating it into the page? Either works; templating is simpler and the review
  page already fetches stats. Going with template injection.
