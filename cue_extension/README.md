# `cue_extension/`

Cue browser extension — Manifest V3, Chromium-first, evidence-backed form filling
against a configurable Cue API instance. The third Cue frontend alongside `cue_ui/`
and `shape_ui/`.

Full spec: `openspec/changes/add-cue-browser-extension/`. Implementation plan:
`~/.claude/plans/kind-churning-lovelace.md`.

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
│   │   ├── registry.ts           runExtraction() — three-tier fall-through
│   │   ├── dom-mapping.ts        DOM → BatchSuggestItem helpers (shared)
│   │   ├── google-forms.ts
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
npm run build       # bundles to dist/chrome/
npm run typecheck   # tsc --noEmit
npm test            # vitest run
```

## Local install (Chrome / Edge, MVP)

1. Run the Cue API locally (`docker-compose up` from repo root) with
   `EXTENSION_ALLOWED_ORIGINS=chrome-extension://<your-extension-id>` set in the
   environment. The extension ID is shown on `chrome://extensions` after
   loading unpacked.
2. `npm run build` in this directory.
3. Open `chrome://extensions`, enable Developer mode, click **Load unpacked**,
   choose `dist/chrome/`.
4. Pin the extension to the toolbar.
5. Click the icon to open the popup. Enter your Cue URL, grant the permission
   prompt, log in.
6. Visit a form, click **Analyse this page**.

## Architecture notes

- **No background work.** The MV3 service worker is empty. All orchestration
  happens in the popup while it is open. SSE connections live in the popup;
  closing the popup ends the stream cleanly (no server-side leak).
- **No `<all_urls>`.** `activeTab` is used instead, so the install warning is
  the small "may read data on the current site when you use the extension"
  rather than the alarming "all sites" variant. This matches user-triggered
  operation and makes store review smoother.
- **`browser.*` via webextension-polyfill.** Single namespace across Chrome,
  Edge, and (Phase E) Firefox.
- **JWT in `browser.storage.local`.** Token rotation/refresh is out of scope
  for v1; on 401 the user logs in again.
- **PII posture.** The audit trail records URL + item count + model name only.
  Form field values and the page text supplied to the LLM fallback are never
  persisted to audit; that posture is enforced server-side (see
  `tests/test_extract_form_api.py::TestAudit`).

## Phased build status

This is Phase B (MVP). Subsequent phases — see the plan:

- Phase C: end-to-end manual validation against real forms.
- Phase D: Microsoft Forms extractor (`forms.office.com`, `forms.cloud.microsoft`).
- Phase E: Firefox parity (build target + manifest gecko id).
- Phase F: CWS + AMO unlisted distribution, deployment docs.

## What's not in v1

- Icons (browser default is used; replace before Phase F store submission).
- Microsoft Forms — Phase D.
- Firefox build — Phase E.
- Token refresh / rotation.
- Quill / rich-text write-back beyond `contenteditable`.
- Safari — separate Xcode + App Store track; deferred per proposal.
