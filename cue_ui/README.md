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
2. Upload a QSF/LSS survey file → lands on document upload page
3. Upload a PDF (optional) → or click **Skip**
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
| `static/review-state.js` | localStorage helper (accept/edit/dismiss state) |
