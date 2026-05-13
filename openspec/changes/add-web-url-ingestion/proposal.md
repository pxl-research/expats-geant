# Change: Allow respondents to add a web URL as a source

## Why

Pilot users have reported that some of the information they want to cite in a Cue
session lives on the web rather than on a local document — institutional policy
pages, government regulations published as PDFs, news articles, Wikipedia entries.
Today they have to download each page, convert it to a supported format, and upload
it manually. That friction discourages people from citing genuinely useful sources.

The current ingestion paths (`POST /upload`, `POST /upload-text`) cover files and
pasted text but not URLs. Adding URL ingestion gives respondents a one-step
"paste URL → preview what we extracted → confirm" flow, with the same chunking,
embedding, citation, and audit behaviour as existing sources.

Web ingestion has real privacy implications (server-side fetches expose the
deployment's IP and the user's intent to third-party origins), so the feature is
**off by default at the operator level** and SHALL also require an explicit
per-session opt-in by the respondent before any URL is fetched.

## What Changes

- **Cue API**
  - New `POST /web/preview` endpoint: accepts a URL, fetches it, extracts content,
    returns a preview (title, source URL, extracted text length, first ~500 chars,
    metadata, content-type) without committing anything to the vector store.
  - New `POST /web/ingest` endpoint: accepts a URL the user has just previewed,
    re-fetches if the preview cache TTL has expired, ingests the extracted content
    into the session vector store, and records the fetch in the audit log.
  - Content-type routing on fetch:
    - `text/html` → **Trafilatura** with `favor_precision=True`, markdown output.
    - `application/pdf`, `application/vnd.openxmlformats-officedocument.*`,
      `text/plain`, `text/markdown` → existing **MarkItDown** path (same as file
      upload).
    - Anything else → reject with a clear error.
  - Re-ingest semantics: if the same URL has already been ingested in the session,
    the old chunks are deleted before the new ones are ingested (**overwrite**).
    Audit log records both fetches.
  - New environment flag `CUE_WEB_INGEST_ENABLED` (default `false`). When unset or
    `false`, both endpoints return HTTP 403.
  - HTTP fetch hardening: 10 s timeout, no retry, polite User-Agent
    (`Cue/0.x (+contact-url)`), size capped by the existing `max_file_size_mb`.
  - Audit log: each fetch records URL, timestamp, content-type, extracted byte
    length, and a `likely_js_rendered` flag (set when extracted text is
    suspiciously short for the response body size).
- **Cue UI**
  - New "Add web source" panel on the documents page and inside the mid-review
    upload widget (introduced by `add-late-document-uploads`).
  - URL input → preview view (title, hostname, extracted-text length, first 500
    chars, any warnings) → **Add as source** or **Discard** buttons. The text is
    only ingested on **Add as source**.
  - Per-session **Allow web sources** toggle (visible only when the operator flag
    is on). Toggle defaults to off; URL preview/ingest endpoints SHALL be rejected
    on the UI side while the toggle is off, mirroring the API-side enforcement.
  - When the operator flag is off, the panel is hidden entirely (no toggle, no
    URL input). The privacy/EULA endpoint reflects whether web ingestion is
    enabled for the deployment.
  - Re-ingest UX: if the URL already exists in the session, the preview view shows
    "You ingested this URL on [date]. Confirming will replace the previous version."
- **Documentation**
  - `docs/CUE_API.md`: document the two new endpoints, the operator flag, and the
    audit-log fields.
  - `docs/OPERATOR_RUNBOOK.md`: privacy considerations of enabling web ingestion;
    decision checklist for the operator.

## Impact

- Affected specs: `document-ingestion`, `survey-ui`
- Affected code:
  - `cue_api/routes/web.py` (new) — preview + ingest endpoints.
  - `cue_api/web_fetch.py` (new) — fetch + content-type routing + Trafilatura
    extractor; preview cache.
  - `cue_api/ingest.py` — small helper to ingest pre-extracted text under a URL
    source name; delete-by-source helper for overwrite semantics.
  - `cue_api/api.py` — register router; expose `web_ingest_enabled` on app state.
  - `m_shared/utils/audit.py` — new event type `WEB_FETCH` (URL, content-type,
    bytes, js-hint flag).
  - `cue_ui/routes/web.py` (new) — UI proxy for preview + ingest; renders preview
    partial.
  - `cue_ui/templates/documents.html`, `cue_ui/templates/survey.html`,
    `cue_ui/templates/partials/web_preview.html` (new) — UI affordances.
  - `cue_ui/static/web.js` (new) — paste-URL flow and preview-confirm wiring.
  - `requirements.txt` — add `trafilatura`.
  - `.env.example` — document `CUE_WEB_INGEST_ENABLED`.
- Out of scope:
  - Active web search (Google, Bing, SearXNG, etc.).
  - JavaScript-rendered pages (Selenium/Playwright). Failures surface a clear
    "save as PDF and upload" fallback instead.
  - LLM rewrite or summarisation of extracted text (preserves citation precision).
  - Operator allowlist/blocklist of domains.
  - `robots.txt` compliance (user-pasted URL implies user-authorised fetch).
- Sequencing: this proposal assumes `add-late-document-uploads` ships first, so
  the mid-review upload widget already exists to host the URL panel. If the order
  flips, the `survey-ui` delta needs minor adjustments but no rework.
