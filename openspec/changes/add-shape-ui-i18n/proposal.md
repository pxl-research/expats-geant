# Change: Add i18n support to Shape UI

## Why

The Shape UI supports 7 survey languages (en, nl, fr, de, es, it, pt) and the LLM now
responds in the selected language, but all UI chrome (buttons, labels, headings, error
messages) and validation annotations remain hardcoded in English. This breaks the
language immersion for non-English users and makes the product feel unfinished for the
GEANT TNC demo targeting a multilingual European audience.

## What Changes

- **New shared i18n module** (`m_shared/i18n.py`): JSON-based translation loader with
  a `t(lang, key, **kwargs)` function supporting interpolation and English fallback.
- **Translation files** (`shape_ui/i18n/*.json`): one JSON file per supported language,
  keyed by dotted string identifiers (e.g. `chat.send`, `export.download`).
- **Shape UI templates**: all ~95 hardcoded English strings replaced with `{{ t(key) }}`
  calls via a Jinja2 global function.
- **Shape UI Python routes**: ~17 error/status messages rendered via `t()`.
- **Shape UI JavaScript**: ~5 hardcoded strings replaced with a lightweight JS
  translation object injected from the server.
- **API error codes**: Shape API error responses gain a stable `code` field alongside
  the existing English `message`. The API itself stays English; the UI translates based
  on the code.
- **Structured validation issues**: the chat endpoint returns validation issues as
  structured data alongside the reply text, instead of injecting English wrapper text
  ("I also noticed: ...") into the LLM response. The UI renders and translates them.
- **Language resolution**: the UI language follows the session's style profile language
  setting. No separate UI language selector is introduced.

## Impact

- Affected specs: `shape-ui`, `questionnaire-design`
- Affected code:
  - `m_shared/i18n.py` (new)
  - `shape_ui/i18n/*.json` (new, 7 files)
  - `shape_ui/router.py`
  - `shape_ui/templates/*.html` (12 files)
  - `shape_ui/static/js/*.js` (2 files)
  - `shape_ui/routes/*.py` (3 files)
  - `shape_api/routes/chat.py`
  - `shape_api/conversation.py`
- Not in scope: Cue UI i18n (future effort), API message translation, LLM system
  prompts (already in English by design)
