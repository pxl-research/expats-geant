# Cue UI: Survey Review Frontend

Server-rendered FastAPI app (Jinja2 + HTMX) that lets respondents upload a survey,
optionally upload source documents, review AI suggestions per question, and submit responses
back to the originating platform.

Communicates with Cue exclusively via HTTP — imports nothing from `cue_api/` or `m_shared/`.

## Running

### With Docker Compose (recommended)

```bash
docker compose up --build
```

- Cue API: http://localhost:8001
- Cue UI frontend:  http://localhost:8002

### Standalone (dev)

```bash
pip install -r cue_ui/requirements.txt

# Point at a running Cue instance
export CUE_API_URL=http://localhost:8001

python -m uvicorn cue_ui.main:app --host 127.0.0.1 --port 8002 --reload
```

## Manual E2E Test Flow

With the full stack running (`docker compose up`):

1. Visit http://localhost:8002 → redirected to Keycloak login
2. Upload a QSF/LSS survey file → lands on the **Add Source Documents** page
3. (Optional) add sources via any of the four cards (Files / Web / Paste text /
   review the running list at the bottom), then click **Continue** —
   ingestion is per-card and immediate; no batched submit
4. Suggestions load inline via HTMX
5. Accept / dismiss suggestions — check `localStorage` in browser devtools (key: `review-<session_id>`)
6. Refresh mid-review → confirm state is restored from localStorage
7. Submit (if adapter supports it) or verify display-only banner
8. Test session expiry: manually expire session → verify expiry page + localStorage cleared

## Unit / Integration Tests

```bash
pytest tests/test_ui_*.py -v
```

All cue_ui tests mock external HTTP calls (respx) — no running server required.

## Adding sources

### Documents page (before review)

The pre-review **Add Source Documents** page (`templates/documents.html`)
renders four cards:

1. **Files** — multi-file picker; PDF/DOCX/PPTX/TXT/MD/XLS/images.
2. **Add a Web Source** — paste a URL → preview the extracted content →
   confirm to ingest. Hidden entirely when `CUE_WEB_INGEST_ENABLED=false`
   on the API; visible-but-gated when the operator flag is on but the
   per-session "Allow web sources" toggle is off.
3. **Paste Text** — textarea + optional label, for leftover snippets.
4. **Your Sources** — live-refreshing list of everything ingested in the
   session + the **Continue** button (disabled while any add is in flight).

Each card ingests immediately via fetch (`/session/{id}/upload-doc`,
`/session/{id}/upload-text-snippet`, `/session/{id}/web/preview` →
`/session/{id}/web/ingest`). Successful adds bump a counter in the sources
list and briefly flash the new row.

### Mid-review widget

The same four blocks (Sources → Files → Web → Text) appear, more compact,
inside a `<details>` panel on the review page so respondents can add a
source after suggestions have already streamed — without losing their
review state.

Each cached suggestion carries a `generated_at` timestamp; the page also
receives a `last_upload_at` snapshot from `GET /session/stats`. When an upload
succeeds, `lastUploadAt` is bumped client-side and `recomputeRegenerateVisibility()`
reveals:

- a per-question **Regenerate** button on any cached suggestion older than
  `lastUploadAt`,
- a bulk **Regenerate untouched (N)** button next to "Accept all" that targets
  questions that are both stale and not yet accepted/dismissed/edited, and
- a bulk **Regenerate empty answers (N)** button for questions where the
  cached suggestion is empty (no answer found) and the user hasn't acted on
  it yet — this one stays visible whenever such questions exist, independent
  of upload staleness.

Both buttons stream from `/session/{id}/regenerate-stream` (a UI proxy that
mirrors `/suggest-stream` minus the cached-IDs filter); the Cue API itself is
unchanged. Re-suggesting an item overwrites its `cached_suggestions.json`
entry — accepted/dismissed answers, by contrast, are excluded from the bulk
flow to avoid clobbering deliberate review decisions.

## Architecture

```
Browser ──► cue_ui (FastAPI, port 8002)
                │  Jinja2 + HTMX, server-rendered
                │  HttpOnly cookie stores JWT
                │
                ▼ httpx + Bearer JWT
            cue_api API (port 8001)
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | App factory, static file mount |
| `router.py` | Router hub: shared templates, helpers, sub-router registration |
| `routes/auth.py` | Auth routes (login, callback, logout) |
| `routes/upload.py` | Landing page, survey file upload, API import |
| `routes/review.py` | Document upload, review page, SSE suggestion stream, submit |
| `api_client.py` | httpx wrapper — one function per Cue endpoint |
| `auth.py` | HttpOnly cookie read/write, OAuth redirect helpers |
| `templates/survey.html` | Main review page with question controls |
| `templates/documents.html` | Pre-review four-card source page (Files / Web / Text / Your Sources + Continue) |
| `static/review-state.js` | localStorage helper (accept/edit/dismiss state) |
| `static/documents.js` | Documents-page per-card fetch ingest, sources list refresh + flash |
| `static/web.js` | URL preview/ingest flow; emits `web-ingest-start`/`end` events |
