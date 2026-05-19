# Design: Web URL ingestion

## Context

The current ingestion surface offers two paths:

- `POST /upload` — file upload, routed through MarkItDown
  (`cue_api/routes/documents.py:22`).
- `POST /upload-text` — plain-text snippet under an optional label
  (`cue_api/routes/documents.py:109`).

Both feed into `ingest_files_into_store` / `ingest_text_into_store` in
`cue_api/ingest.py`, which chunks, embeds, and stores under a session-scoped
ChromaDB collection.

Pilot feedback identified URLs as a meaningful gap: respondents want to cite web
pages (policy, regulation, articles) and online-hosted PDFs without manual
download. The example code referenced for this work uses raw `markdownify`, which
produces noisy output (nav, ads, cookie banners). We want something better.

## Goals / Non-Goals

**Goals**
- One-step "paste URL → preview → ingest" flow that produces a citation-ready
  source in the same shape as a file upload.
- Clean content extraction via **Trafilatura** for HTML; existing **MarkItDown**
  path for binary/text formats reachable by URL.
- Explicit user authorisation: the user pastes the URL, sees what was extracted,
  and confirms before any chunks reach the vector store.
- Privacy-first defaults: feature disabled per deployment by default; per-session
  opt-in required by the respondent.
- Truthful audit trail: every fetch logged, regardless of whether the user
  confirms ingestion.

**Non-Goals**
- Active web search (Google CSE / SearXNG / DuckDuckGo). Defer to a future
  proposal pending pilot feedback.
- JavaScript-rendered page support. The Trafilatura docs are explicit that
  rendering belongs in a separate layer (Playwright/Selenium), which would add
  significant Docker bloat and concurrency complexity for a minority of pilot
  use-cases. Failures degrade gracefully with a "save as PDF" message.
- LLM rewrite/summarisation. Citation precision is core to Cue; rewriting breaks
  chunk-to-source provenance.
- Domain allowlist/blocklist. YAGNI for PoC; easy to add later.
- `robots.txt` compliance. The user paste authorises the fetch; this is not a
  crawler.

## Decisions

### Decision 1: Two-endpoint preview/ingest flow, not one-step

`POST /web/preview` fetches and extracts but does not store. `POST /web/ingest`
takes the same URL, replays the fetch if the preview cache TTL (60 s) has
expired, and writes chunks. Audit log records both.

*Why split:* Web pages are noisy and unpredictable. Showing the user a 500-char
preview before committing chunks is the simplest answer to "sourcing webpages is
a pain — content does not always filter through nicely." If the preview is
garbage, the user discards without polluting their session.

*Why not just cache the extracted text and skip the re-fetch on ingest:* We do
cache it, with a 60 s TTL. After that, we re-fetch. A user who paused for coffee
between preview and confirm gets a fresh snapshot, which is the more honest
behaviour and avoids stale results when pages update frequently.

### Decision 2: Content-type routing — Trafilatura for HTML, MarkItDown for the rest

After fetch, inspect `Content-Type` header **and** sniff magic bytes (defence
against mislabelled servers). Route:

| Content-Type | Extractor |
|---|---|
| `text/html`, `application/xhtml+xml` | Trafilatura, `favor_precision=True`, `output_format="markdown"`, `include_links=False`, `include_images=False`, `deduplicate=True` |
| `application/pdf` | MarkItDown |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (`.docx`) | MarkItDown |
| `application/vnd.openxmlformats-officedocument.presentationml.presentation` (`.pptx`) | MarkItDown |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (`.xlsx`) | MarkItDown |
| `text/plain`, `text/markdown` | Pass through as snippet |
| Anything else (`image/*`, `application/zip`, `video/*`, …) | Reject with clear error |

*Why two extractors:* Trafilatura is purpose-built for web article extraction and
beats MarkItDown on HTML noise. MarkItDown already handles the binary formats
that file upload accepts; reusing it costs almost nothing and ensures URL-PDF
behaves identically to upload-PDF.

*Why no Selenium for HTML:* covered above. If Trafilatura yields suspiciously
little text (< 200 chars after extraction), we set a `likely_js_rendered` flag
in the audit log and return a warning in the preview ("This page may require a
browser to render; saving as PDF and uploading is a reliable workaround.").

### Decision 3: Re-ingest semantics are *overwrite*, not *skip* or *append*

Today, file uploads with a duplicate label are silently **skipped**
(`document-ingestion` spec, "Duplicate label is skipped"). For URLs, that
behaviour is wrong: the user often re-ingests precisely because the page has
changed, or the first fetch failed.

We diverge:
- Re-ingest of an existing URL **deletes the prior chunks** for that URL source
  and writes the freshly-fetched ones.
- The preview screen surfaces "You ingested this URL on [date]. Confirming will
  replace the previous version." so the action is not surprising.
- The audit log retains both fetch events (it is append-only — same pattern as
  the suggestion answer report).
- Existing accepted suggestions in `review_state.json` are unaffected: their
  citation text is preserved verbatim, even though the underlying chunks have
  been replaced. Users can manually click the per-question **Regenerate** button
  (from `add-late-document-uploads`) to re-derive suggestions against the new
  chunks.

*Why diverge from the file-upload "skip" default:* a URL is identity, not
content. "I added the same URL again" almost always means "I want the current
content of this page," whereas "I uploaded the same file twice" usually means
"oops, I forgot I already did that." Different intent, different default.

### Decision 4: Privacy gate is two layers — operator env flag and per-session toggle

- **`CUE_WEB_INGEST_ENABLED`** (default `false`). When unset or `false`, the
  Cue API returns HTTP 403 from both `/web/preview` and `/web/ingest`, and the
  UI hides the "Add web source" panel entirely. The operator decides whether the
  feature is even available in their deployment.
- **Per-session toggle** ("Allow web sources"). Visible only when the operator
  flag is on; defaults to off; persisted as session metadata. The UI surfaces
  why the feature is gated (one-line explanation about server-side fetches) so
  the respondent makes an informed choice.

*Why two layers:* The operator gate is a deployment-wide policy decision (does
this institution allow outbound fetches at all?). The session toggle is a
respondent-level consent decision (am I OK with this for this session?). The
project's privacy-first stance demands both — operators set the boundary,
respondents opt in inside it.

### Decision 5: Preview cache scoped to session + normalised URL, 60 s TTL

- Cache key: `(session_id, normalise(url))` where normalisation strips fragment
  (`#section`) and lowercases scheme/host. Query parameters are *kept* (often
  load-bearing).
- TTL: 60 s. Long enough to cover the human round-trip "look at preview, click
  confirm." Short enough that a "coffee break" forces a re-fetch.
- Storage: in-process dict, no Redis. Sessions are bound to one process today
  (per the operator runbook); if Cue moves to multi-process, the cache becomes
  a cache miss, not a correctness bug.

*Why not persist the cache:* one extra moving part for ~60 s of value. The
re-fetch on miss is the same code path, just slightly slower.

### Decision 6: HTTP fetch hardening

- **Timeout**: 10 s connect + read. Anything slower than that is unlikely to
  yield useful content in a survey flow.
- **No retries**: a failed fetch surfaces an error. The user can retry manually.
  Retries silently double the network footprint and obscure failure modes.
- **User-Agent**: `Cue/0.x (+https://github.com/pxl-research/expat-geant)`.
  Identifies us politely so sites can rate-limit or block us reasonably. Default
  `python-requests` is widely blocked.
- **Size cap**: respect the existing `max_file_size_mb` (default 50 MB). Same
  envelope as file uploads.
- **Redirect handling**: follow up to 5 redirects. Record the *final* URL as the
  source, but log both initial and final in the audit trail.
- **No proxy**: synchronous server-side fetch. No outbound proxy for now; that
  belongs in a deployment-level networking decision, not an application
  setting.

### Decision 7: Source naming and citation metadata

- For HTML: source name = page title (from Trafilatura metadata) if present,
  else `hostname/path`. Truncate to 100 chars. URL preserved verbatim in chunk
  metadata for citation rendering.
- For non-HTML (PDF, DOCX, …): source name = URL path basename
  (e.g. `regulation_2024_03.pdf`); URL preserved in chunk metadata.
- All chunks for a URL share a `source_url` metadata field. This is what the
  delete-by-source helper uses for overwrite semantics.

### Decision 8: Failure UX is explicit and helpful

- **Network error / timeout**: "Could not reach this URL within 10 s. Check the
  URL or try again."
- **HTTP 4xx/5xx**: include the status code and any meaningful response text
  (truncated). "The page returned HTTP 403 (Forbidden) — it may require a
  login."
- **Unsupported content type**: list the type returned and the types we accept;
  suggest downloading + uploading.
- **Empty / suspiciously short extraction**: surface a warning in the preview;
  the user can still confirm if they want, but they see "We only extracted 87
  characters. This page may require a browser to render. Save as PDF and upload
  for reliable results."
- **Page too large**: reject with the limit and a "download + upload" hint.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| User pastes a sensitive internal URL → server logs/audit retain it | Audit trail is intentional; mention it explicitly in the per-session opt-in copy ("URLs you add will be logged in your audit report") |
| User pastes a tracking/redirect URL → final URL differs surprisingly | Audit logs both initial and final; preview displays the final URL prominently |
| Page is paywalled or geo-blocked → useless extraction | `likely_js_rendered` flag also fires for low-content pages; preview warning surfaces it |
| Trafilatura misclassifies and drops the actual content | `favor_precision=True` is safer than `favor_recall`. If users hit this often in pilot, revisit per-page strategy. |
| User overwrites a URL whose chunks were cited in already-accepted suggestions | Suggestion *text* is preserved in review state; only re-derivation against the new chunks requires manual Regenerate. Audit log preserves the prior fetch. Worst case: user re-confirms a suggestion based on text they can still read. Acceptable. |
| Pilot site IP gets rate-limited by frequently-fetched origins | 10 s timeout + no retries keeps us polite. If pilot triggers blocks, add per-domain in-process throttle later. |
| Trafilatura adds significant Python dep | ~5 MB install. Acceptable. No native compilation. |

## Migration Plan

None required:
- New endpoints are additive.
- Existing file/text upload paths unchanged.
- `CUE_WEB_INGEST_ENABLED` defaults to `false`, so existing deployments behave
  identically until the operator opts in.

## Open Questions

- Should we strip query parameters in URL normalisation for cache keying? Some
  pages use them for pagination (load-bearing), others use them for tracking
  (UTM, fbclid). Going with **keep all query params** to avoid wrong behaviour
  on paginated content; UTM noise just means slightly higher cache miss rates,
  not incorrect content. Revisit if pilot data shows noisy cache key drift.
- Do we want a per-session count cap on URL ingests (e.g. max 20)? Probably not
  for MVP — the size cap and operator gate already bound the blast radius. Add
  if abuse emerges.
