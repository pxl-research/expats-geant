# Change: Add Cue browser extension

## Why

Cue today reaches respondents through `cue_ui/`, which only works for surveys an
institution controls and can ingest via `POST /surveys/import` (LSS / QSF / QTI /
SurveyMonkey JSON). The long tail of forms users encounter daily — Google Forms,
Microsoft Forms, vendor portals, government sites, internal HR systems — is
unreachable. A browser extension that scrapes the active page's form and writes
evidence-backed answers (with citations) back into the page closes that gap. It
becomes the third Cue frontend alongside `cue_ui/` and `shape_ui/`, sharing the
Cue API and document store but distributed independently to end-users' browsers.

## What Changes

- **New `cue_extension/` package**: MV3 browser extension targeting Chrome, Edge,
  and Firefox from a single codebase. Three execution contexts — popup
  (settings, document upload, trigger, citation rendering), content script (DOM
  scraping + write-back), and a Cue API client that speaks to a configurable
  instance.
- **New `cue-extension` capability spec** describing extension behaviour:
  manifest posture, extractor registry, popup lifecycle, write-back contract,
  privacy posture.
- **Adapter pattern for form extraction**, mirroring `m_shared/adapters/`. Each
  extractor self-identifies via `detect(url, document)` and emits
  `BatchSuggestItem[]` (the existing wire DTO). The registry tries extractors in
  priority order, falling back to the next on miss.
  - **Google Forms extractor** — `docs.google.com/forms/*`, DOM signatures
    `[role="listitem"]` + `data-params`.
  - **Microsoft Forms extractor** — `forms.office.com`, `forms.cloud.microsoft`,
    `data-automation-id` selectors.
  - **Semantic HTML extractor (deterministic fallback)** — walks
    `<label>`/`<input>`/`<select>`/`<textarea>` for plain `<form>` elements.
  - **LLM-assisted extractor (third tier, optional)** — calls a new
    `POST /extract-form` endpoint with page text when semantic heuristics fail.
- **Full session lifecycle inside the extension**: log in to the configured Cue
  instance, upload source documents, start a session, fill forms. Users never
  have to visit `cue_ui/`. Pasting an existing session JWT is not supported in
  v1.
- **User-triggered only**: extractors run on explicit popup-button click. No
  background form-watching, no on-page injection without user action.
- **New Cue API endpoint** `POST /extract-form` (in `answer-suggestion`): accepts
  page text + URL, returns `BatchSuggestItem[]`. Reserved for the LLM-assisted
  fallback; auditable like any other suggestion call.
- **CORS allow-list for extension origins** (in `auth-security`): configurable
  list of `chrome-extension://<id>` and `moz-extension://<uuid>` origins.
  Defaults reject; operator opts in per deployment.
- **Streaming suggestion delivery is the extension's default**: the popup
  consumes `POST /suggest/stream` so each field populates as its answer lands.
  `POST /suggest/batch` remains available as a fallback.
- **Distribution**: Chrome Web Store unlisted listing, Mozilla AMO unlisted
  listing, optional enterprise force-install policy snippet. Safari deferred.

## Impact

- **Affected specs**:
  - **NEW**: `cue-extension` (full capability)
  - **MODIFIED**: `answer-suggestion` (adds `POST /extract-form`)
  - **MODIFIED**: `auth-security` (adds extension-origin CORS allow-list)
- **Affected code**:
  - `cue_extension/` — new package (TypeScript / JS), MV3 manifest, popup, content
    script, extractor modules, Cue API client, write-back dispatcher
  - `cue_api/api.py` — register `POST /extract-form` route
  - `cue_api/rag_pipeline.py` or new `cue_api/extract.py` — LLM-assisted form
    extraction helper
  - `cue_api/middleware.py` (or wherever CORS is configured) — extension-origin
    allow-list
  - `m_shared/auth/` — CORS configuration surface
  - `docker-compose.yml` — no change (extension is browser-side)
  - `docs/DEPLOYMENT.md` — extension install + distribution section
  - `docs/CUE_API.md` — `/extract-form` endpoint reference
- **Not in scope**:
  - Safari support — deferred. Distribution requires a Mac, Xcode wrapping via
    `xcrun safari-web-extension-converter`, an Apple Developer membership
    (~$99/yr individual or ~$299/yr enterprise), and App Store / TestFlight
    review cycles. Cost does not pencil for a PoC where Chrome and Firefox
    cover the great majority of researchers.
  - Typeform / JotForm / SurveyMonkey-respondent-UI extractors (post-PoC)
  - Pasting an existing `cue_ui/` session JWT (full lifecycle only in v1)
  - Multi-page / SPA pagination handling beyond what each extractor needs for
    its target platform
  - Background / proactive form detection (user-triggered only)
