# `cue_extension/`

Cue browser extension — Manifest V3, Chromium + Firefox, evidence-backed form
filling against a configurable Cue API instance. The third Cue frontend
alongside `cue_ui/` and `shape_ui/`.

This README is the **developer entry point** for editing the extension source.
For installation, configuration, store-publication, and smoke-testing instructions,
see the canonical operator doc: [`docs/DEPLOYMENT.md` → Cue Browser Extension](../docs/DEPLOYMENT.md#cue-browser-extension).
For the server-side API contract, see [`docs/CUE_API.md` → Extract Form Fields](../docs/CUE_API.md#extract-form-fields-llm-fallback).
Full spec: `openspec/changes/add-cue-browser-extension/`.

## What it does

1. User opens the popup, configures the Cue base URL (one-time, grants host
   permission for that origin only), and logs in via `POST /auth/token`.
2. User uploads source documents through the popup → `POST /upload`.
3. User opens the form they want to fill, clicks **Analyse this page**.
4. The content script is injected via `chrome.scripting.executeScript` and runs
   the three-tier extractor registry:
   - **Google Forms** (`docs.google.com/forms/*` with `[role="listitem"]` containers)
   - **Semantic HTML** — walks `<form>` + form controls with label resolution
   - **LLM fallback** — `POST /extract-form` (only when prior tiers return zero)
5. Items are streamed through `POST /suggest/stream`; each suggestion populates
   its target element via the write-back dispatcher.
6. Citations render in the popup; the user can download the audit report.

User-triggered only. Nothing leaves the browser without an explicit click.

## Project layout

```
cue_extension/
├── package.json
├── tsconfig.json
├── build.mjs              esbuild bundling for 3 entry points
├── vitest.config.mjs      jsdom + vitest
├── manifest.json          MV3, activeTab + storage + scripting
├── src/
│   ├── types.ts                  Mirror of cue_api/models.py wire types
│   ├── api/
│   │   ├── client.ts             Cue REST client (auth/upload/suggest/extract/audit)
│   │   └── sse.ts                fetch + ReadableStream SSE parser
│   ├── extractors/
│   │   ├── base.ts               Extractor interface + ExtractHelpers
│   │   ├── registry.ts           runExtraction() — priority fall-through
│   │   ├── dom-mapping.ts        DOM → BatchSuggestItem helpers (shared)
│   │   ├── google-forms.ts
│   │   ├── microsoft-forms.ts
│   │   ├── semantic-html.ts
│   │   └── llm-fallback.ts
│   ├── writers/dispatcher.ts     applySuggestion(element, suggestion)
│   ├── content/inject.ts         in-page agent — extract + write-back
│   ├── background/sw.ts          empty MV3 service worker
│   └── popup/
│       ├── popup.html
│       ├── popup.css
│       └── popup.ts              full session lifecycle UI
├── tests/                        jsdom + vitest unit tests
└── dist/chrome/                  build output (gitignored)
```

## Build, typecheck, test

```bash
cd cue_extension
npm install
npm run build         # bundles to dist/chrome/
npm run build:firefox # bundles to dist/firefox/
npm run build:all     # both targets
npm run typecheck     # tsc --noEmit
npm test              # vitest run
```

## Loading the unpacked build

For full configuration steps — `EXTENSION_ALLOWED_ORIGINS`, container
restart, smoke-test, store publication — see
[`docs/DEPLOYMENT.md` → Cue Browser Extension](../docs/DEPLOYMENT.md#cue-browser-extension).
The minimum dev loop:

- **Chrome / Edge**: `npm run build:chrome` → `chrome://extensions` → enable
  Developer mode → **Load unpacked** → `dist/chrome/`.
- **Firefox 121+**: `npm run build:firefox` →
  `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on…** →
  `dist/firefox/manifest.json`.

In both cases, add the resulting `chrome-extension://<id>` or
`moz-extension://<gecko-id>` origin to `EXTENSION_ALLOWED_ORIGINS` in
`.env` and `docker compose up -d cue-api`.

## Architecture notes

- **No background work.** The MV3 service worker is empty. All orchestration
  happens in the popup while it is open. SSE connections live in the popup;
  closing the popup ends the stream cleanly (no server-side leak).
- **No `<all_urls>`.** `activeTab` is used instead, so the install warning is
  the small "may read data on the current site when you use the extension"
  rather than the alarming "all sites" variant. This matches user-triggered
  operation and makes store review smoother.
- **`browser.*` via webextension-polyfill.** Single namespace across Chrome,
  Edge, and Firefox.
- **JWT in `browser.storage.local`.** Token rotation/refresh is out of scope
  for v1; on 401 the user logs in again.
- **PII posture.** The audit trail records URL + item count + model name only.
  Form field values and the page text supplied to the LLM fallback are never
  persisted to audit; that posture is enforced server-side (see
  `tests/test_extract_form_api.py::TestAudit`).

## Phased build status

Shipped: Phase A (server `/extract-form` + CORS), Phase B (MVP Chromium build,
three extractors), Phase C (end-to-end validation + UX fixes), Phase D
(Microsoft Forms extractor), Phase E (Firefox parity), Phase F (deployment +
API docs). Remaining for Phase F: store listings (CWS + AMO unlisted) and icon
assets — both gated on the operator initiating the dev-account registrations.

## What's not in v1

- Token refresh / rotation.
- Quill / rich-text write-back beyond `contenteditable`.
- Safari — separate Xcode + App Store track; deferred per proposal.
