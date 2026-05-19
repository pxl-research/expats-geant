# Tasks

## 1. Dependencies and configuration

- [x] 1.1 Add `trafilatura` to `requirements.txt` (pin a known-good minor version)
- [x] 1.2 Add `CUE_WEB_INGEST_ENABLED=false` to `.env.example` with a comment
  describing privacy implications
- [x] 1.3 Update `docs/DEPLOYMENT.md` env-var table with the new flag

## 2. Cue API — fetch + extraction core

- [x] 2.1 Create `cue_api/web_fetch.py` with a `fetch_url(url)` function:
  10 s timeout, polite User-Agent, max 5 redirects, size cap from
  `max_file_size_mb`; returns `(final_url, content_type, body_bytes,
  initial_url)`
- [x] 2.2 Add a content-type router that dispatches HTML to Trafilatura and
  binary/text types to the existing MarkItDown path
- [x] 2.3 Trafilatura extraction wrapper: `favor_precision=True`,
  `output_format="markdown"`, `include_links=False`, `include_images=False`,
  `deduplicate=True`; returns extracted text + metadata (title, hostname,
  optional author/date)
- [x] 2.4 Compute `likely_js_rendered` heuristic: extracted text length < 200
  chars on an HTML response of > 5 KB
- [x] 2.5 In-process preview cache, 60 s TTL, keyed by
  `(session_id, normalised_url)`; normalisation strips fragment, lowercases
  scheme/host, keeps query string
- [x] 2.6 Unit tests: HTML happy path (Wikipedia or fixture HTML),
  PDF happy path (small fixture PDF), unsupported MIME (image), oversize
  rejection, timeout, redirect-final-URL recorded

## 3. Cue API — preview/ingest endpoints

- [x] 3.1 Create `cue_api/routes/web.py` with `POST /web/preview` and
  `POST /web/ingest`
- [x] 3.2 Both endpoints check `app.state.web_ingest_enabled` and return HTTP
  403 with a clear message when disabled
- [x] 3.3 Both endpoints check per-session opt-in flag and return HTTP 403 when
  the session has not granted consent
- [x] 3.4 `/web/preview` returns: `final_url`, `initial_url`, `title`,
  `hostname`, `content_type`, `extracted_chars`, `preview_text` (first 500
  chars), `warnings` (list including `likely_js_rendered` if set), and a
  `already_ingested_at` field if this URL is already present in the session
- [x] 3.5 `/web/ingest` looks up the preview cache; on miss, re-fetches; on
  re-ingest, deletes prior chunks for the same `source_url` then writes new
  ones; emits a `WEB_FETCH` audit event in either case
- [x] 3.6 Register the router in `cue_api/api.py` and expose
  `web_ingest_enabled = os.getenv("CUE_WEB_INGEST_ENABLED", "false").lower() ==
  "true"` on `app.state`
- [x] 3.7 Add `WEB_FETCH` event type to `m_shared/utils/audit.py` with fields:
  `url`, `final_url`, `content_type`, `extracted_chars`,
  `likely_js_rendered`, `ingested` (bool — false for preview-only)
- [x] 3.8 Add a per-session "allow web sources" toggle endpoint
  (`PUT /session/web-consent`) and persist as session metadata
- [x] 3.9 Integration tests: preview-then-ingest happy path; preview-only;
  re-ingest replaces chunks; gate-off returns 403; per-session consent missing
  returns 403; same URL ingested twice → exactly one source in vector store

## 4. Ingestion plumbing

- [x] 4.1 In `cue_api/ingest.py`, add a helper that ingests pre-extracted text
  under a given source name + `source_url` metadata (reuses existing chunking
  + embedding)
- [x] 4.2 Add a `delete_by_source_url(store, source_url)` helper that removes
  all chunks tagged with the given URL; used by re-ingest overwrite
- [x] 4.3 Source name derivation: HTML → page title (truncated to 100 chars)
  or hostname+path fallback; non-HTML → URL path basename

## 5. Cue UI — paste/preview/ingest flow

- [x] 5.1 Create `cue_ui/routes/web.py` proxying to `/web/preview` and
  `/web/ingest`
- [x] 5.2 Create `cue_ui/templates/partials/web_preview.html` rendering the
  preview block: title, final URL, content-type pill, first 500 chars
  (collapsed `<details>`), warnings, **Add as source** / **Discard** buttons
- [x] 5.3 Add the "Add web source" panel to `cue_ui/templates/documents.html`
  with a URL input and submit button → fetches preview, swaps in the partial
- [x] 5.4 Add the same panel to the mid-review upload widget in
  `cue_ui/templates/survey.html` (the widget introduced by
  `add-late-document-uploads`)
- [x] 5.5 Create `cue_ui/static/web.js` to wire the URL input → preview
  (fetch + render partial), and **Add as source** → ingest (fetch + close
  preview + refresh document list)
- [x] 5.6 Hide the panel entirely when the operator flag is off (server-side
  template guard, no client-side conditional)
- [x] 5.7 Render the per-session "Allow web sources" toggle below the panel
  when the operator flag is on; toggle off by default; one-line explanation
  ("URLs are fetched by the server and recorded in your audit report.")
- [x] 5.8 Re-ingest UX: preview shows
  "You ingested this URL on [date]. Confirming will replace the previous
  version." when `already_ingested_at` is present
- [x] 5.9 Error states: render an inline error block for each failure type
  listed in `design.md` § Decision 8

## 6. Documentation

- [x] 6.1 Update `docs/CUE_API.md` with the two endpoints, request/response
  shapes, error codes, and the operator flag
- [x] 6.2 Update `docs/OPERATOR_RUNBOOK.md` with a "Should I enable web
  ingestion?" decision checklist (privacy, audit, third-party fetch posture)
- [ ] 6.3 Update `openspec/specs/document-ingestion/spec.md` purpose paragraph
  reference (done via spec deltas, just confirm during archive)

## 7. Validation

- [x] 7.1 `pytest` — full suite green, including the new fixtures
- [x] 7.2 `openspec validate add-web-url-ingestion --strict`
- [ ] 7.3 Manual smoke: enable env flag, opt in per session, paste 3 URLs
  (an HTML article, a PDF, an SPA-only page); verify preview accuracy,
  ingest behaviour, audit-log entries, and the JS-rendered warning
- [ ] 7.4 Manual smoke: re-ingest the same URL; verify the preview warning,
  the prior-chunks deletion, and the audit log retaining both fetches
- [ ] 7.5 Manual smoke: with operator flag off, confirm the panel is absent
  and the API endpoints return 403
