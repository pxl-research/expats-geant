# Shape UI: Survey Authoring Frontend

Server-rendered FastAPI app (Jinja2 + HTMX) that lets administrators create and refine
questionnaires through a conversational AI interface, manage style profiles, and export
surveys to platform-specific formats.

Communicates with Shape exclusively via HTTP — imports nothing from `shape_api/` or `m_shared/`.

## Running

### With Docker Compose (recommended)

```bash
docker compose up --build
```

- Shape API: http://localhost:8003
- Shape UI frontend: http://localhost:8004

### Standalone (dev)

```bash
pip install -r shape_ui/requirements.txt

export SHAPE_API_URL=http://localhost:8003

python -m uvicorn shape_ui.main:app --host 127.0.0.1 --port 8004 --reload
```

## Architecture

```
Browser ──► shape_ui (FastAPI, port 8004)
                │  Jinja2 + HTMX, server-rendered
                │  HttpOnly cookie stores JWT
                │
                ▼ httpx + Bearer JWT
            shape_api API (port 8003)
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | App factory, static file mount, security headers |
| `router.py` | Router hub: shared templates, helpers, sub-router registration |
| `routes/auth.py` | Auth routes (login, callback, logout) |
| `routes/setup.py` | Session setup, style profile configuration |
| `routes/workspace.py` | Chat workspace, survey preview, export |
| `api_client.py` | httpx wrapper — one function per Shape endpoint |
| `auth.py` | HttpOnly cookie read/write, OIDC redirect helpers |
