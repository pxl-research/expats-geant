# Design: Survey Review UI

## Context

The UI must be a standalone consumer of the M-Autofill API. It must not import internal modules
from `m_autofill/` or `m_shared/` directly. This boundary ensures the core API can be used
independently by third-party integrators while the UI remains an optional add-on.

## Goals / Non-Goals

- **Goals:**
  - Render any survey importable by our adapters (LimeSurvey, Qualtrics, QTI, SurveyMonkey)
  - Display suggestions with citations and reasoning inline per question
  - Allow respondents to review and edit suggestions before submission
  - Conditionally enable submission based on adapter capability
  - Remain a proof-of-concept — functional, not production-polished
- **Non-Goals:**
  - Full accessibility compliance (WCAG AA) — noted for future work
  - Mobile-optimised layout — desktop-first for now
  - Multi-language UI — English only for MVP
  - Authentication/SSO for the UI itself — session handled by M-Autofill API

## Module Structure

```
m_ui/
├── main.py           # FastAPI app; mounts static files and template routes
├── router.py         # Page routes: /survey/{id}, /session/{id}/review
├── api_client.py     # Thin HTTP client wrapping M-Autofill API calls
├── templates/
│   ├── base.html
│   ├── survey.html   # Question rendering + suggestion display
│   └── submitted.html
└── static/
    └── ui.js         # Minimal JS for accept/edit/dismiss interactions
```

`m_ui/` has its own `requirements.txt` (or is a separate Docker service). It does NOT share
Python imports with `m_autofill/` — all data flows through HTTP.

## Decisions

- **Tech: Jinja2 + HTMX over a full JS framework.**
  Rationale: keeps the stack consistent (Python/FastAPI throughout), avoids a separate JS build
  pipeline, and is sufficient for the proof-of-concept scope. HTMX handles inline accept/edit
  interactions without a full page reload.

- **Capability check at session start.**
  When the UI loads a survey session, it calls `GET /adapters/{format}/capabilities` and stores
  the result. The submit button is rendered server-side based on this flag — not toggled in JS.

- **Display-only mode is a first-class mode, not a fallback.**
  The UI explicitly renders a "Review mode — submission not available for this platform" banner
  when submit is not supported, rather than silently hiding the button.

- **Suggestions fetched after survey load, not on page load.**
  The survey renders immediately; suggestions are fetched asynchronously (HTMX swap) so the
  user sees the form structure right away and suggestions fill in progressively.

## Risks / Trade-offs

- HTMX unfamiliarity risk → low; syntax is simple HTML attributes, well-documented
- UI and API versioning drift → mitigated by keeping `api_client.py` as the single integration
  point; any API changes only require updating that file
- Docker networking between `m_ui` and `m_autofill` → standard internal service URL via
  environment variable `AUTOFILL_API_URL`

## Open Questions

_All resolved._

- **File upload support?** → Yes, supported. A file upload flow is added as an alternative
  entry point. Uploading a file implies display-only mode — no API credentials means no
  `"submit"` capability. The capability check handles this automatically; no special-casing
  needed in the UI. Flow: upload file + select format → `POST /surveys/import` → survey_id →
  normal suggestion flow in display-only mode.

- **Partial review persistence?** → Yes, via **localStorage** (client-side). Review state
  is UI state, not domain state — the API only cares about final submitted responses, not the
  intermediate accept/dismiss process. Storing it server-side would bleed UI concerns into the
  domain layer, contradicting the separation principle. localStorage key: `review-{session_id}`,
  value: JSON map of `{question_id: {status, current_value}}`. Auto-saved on every interaction
  via a small JS helper (no round-trip needed). Survives page reload and browser restart.
  Outlives the session TTL — on resume after expiry, the UI detects the dead session and shows
  the expiry message; the local state is simply discarded. Trade-off accepted for MVP: state
  is lost if the user clears browser data or uses private browsing.
