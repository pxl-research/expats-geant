# Change: Add survey review UI for suggestion-assisted form completion

## Why

The M-Autofill suggestion engine is headless by design — it returns suggestions and citations via
API. However, presenting raw JSON to a respondent is not a usable workflow. To make the system
accessible without requiring integration work from survey administrators, we need a UI that can:

1. Render a survey from our internal model (fetched via adapter import)
2. Show AI-generated suggestions alongside each question, with citations and reasoning
3. Let the respondent review, accept, or edit each suggestion before committing
4. Submit the final responses back to the originating platform (where the adapter supports it)

Critically, this UI must be **architecturally decoupled** from the suggestion engine. It is a
consumer of the existing API — not an extension of it. The core API must remain usable without
the UI (for programmatic/integration use cases). The UI is an optional, standalone module.

## What Changes

- A new `m_ui/` module is introduced as a separate FastAPI application (or static frontend)
  that calls the existing M-Autofill API endpoints
- The UI renders surveys dynamically from the internal `Survey` model — no hardcoded platform UI
- Suggestions (with citations and LLM reasoning) are displayed inline per question, not as a
  separate results page
- Users can accept suggestions as-is, edit them, or dismiss them before the form is submitted
- The submit button is shown **only** when the active adapter reports `"submit"` in its
  `capabilities()` — otherwise a **display-only mode** is used (suggestions shown for manual
  reference, no programmatic submission)
- Display-only mode is also the default for platforms without write-back support (SurveyMonkey,
  QTI, any future unsupported platform)

## What Does NOT Change

- The M-Autofill core API (`/suggest`, `/sessions`, `/surveys/import`) — no modifications
- The adapter interface — the UI uses `capabilities()` as-is
- Session/response storage — unchanged; UI submits via the same session flow

## Impact

- Affected specs: new capability `survey-ui`; no changes to existing specs
- Affected code: new `m_ui/` top-level module; no changes to `m_autofill/`, `m_shared/`
- Depends on: `refactor-questionnaire-adapters` (adapter capability discovery + submit_responses)
- Tech choice (to be finalised): lightweight server-rendered HTML (Jinja2 + HTMX) served from
  a small FastAPI app inside `m_ui/` — avoids a full JS framework for the proof-of-concept phase
