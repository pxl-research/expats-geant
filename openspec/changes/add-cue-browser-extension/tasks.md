## 1. Scaffold and Tooling

- [ ] 1.1 Create `cue_extension/` package: MV3 `manifest.json` (Chrome + Firefox baseline), `popup/`, `content/`, `background/` (empty service worker), `src/extractors/`, `src/writers/`, `src/api/`, `src/storage/`
- [ ] 1.2 Add `webextension-polyfill` dependency and wrap browser globals so a single `browser.*` API works across Chrome/Edge/Firefox
- [ ] 1.3 Add `browser_specific_settings.gecko.id` to the manifest; verify Chrome silently ignores it
- [ ] 1.4 Add minimal build script (esbuild or rollup) producing per-browser bundles into `cue_extension/dist/{chrome,firefox}/`
- [ ] 1.5 Document local-install steps for Chrome (unpacked) and Firefox (temporary add-on) in `cue_extension/README.md`

## 2. Extractor Registry and Adapters

- [ ] 2.1 Define `Extractor` interface (`detect(url, document)` + `extract(document)`) in `cue_extension/src/extractors/base.js`
- [ ] 2.2 Implement `registry.js`: iterates extractors in declared priority order, returns the first match
- [ ] 2.3 Implement `google-forms.js` extractor — `docs.google.com/forms/*`, `[role="listitem"]` containers, all `BatchSuggestItem` types
- [ ] 2.4 Implement `microsoft-forms.js` extractor — `forms.office.com` and `forms.cloud.microsoft`, `data-automation-id` selectors
- [ ] 2.5 Implement `semantic-html.js` extractor — generic `<form>` walker with label-resolution order (associated `<label>`, parent `<label>`, `aria-label`, `aria-labelledby`, `placeholder`, nearest preceding text)
- [ ] 2.6 Implement `llm-fallback.js` extractor — calls `POST /extract-form` only when prior tiers return zero items; respects an operator-controlled disable setting
- [ ] 2.7 Register all four in `registry.js` with priority order: Google Forms → MS Forms → semantic HTML → LLM-assisted

## 3. Cue API Client

- [ ] 3.1 Implement `cue_extension/src/api/client.js` with `login()`, `uploadDocument()`, `suggestStream()`, `suggestBatch()`, `extractForm()`, `getAuditReport()`
- [ ] 3.2 SSE consumption helper for `POST /suggest/stream` that emits one suggestion per `event: suggestion`
- [ ] 3.3 Automatic batch fallback when SSE connection cannot be established or is closed before completion
- [ ] 3.4 Surface API errors with stable code + human message into the popup UI

## 4. DOM Write-Back Dispatcher

- [ ] 4.1 Implement `cue_extension/src/writers/dispatcher.js` keyed by element kind
- [ ] 4.2 Plain `input` / `textarea` write-back with synthetic `input` + `change` events
- [ ] 4.3 Radio / checkbox group write-back (click the option matching the selected choice id)
- [ ] 4.4 `<select>` write-back
- [ ] 4.5 `input[type="range"]` write-back
- [ ] 4.6 React-controlled input write-back via `nativeInputValueSetter`
- [ ] 4.7 Quill / contenteditable write-back (port from Pixie Lite)

## 5. Popup UX and Full Session Lifecycle

- [ ] 5.1 Implement popup shell (HTML + CSS) with sections for settings, documents, trigger, and citations
- [ ] 5.2 Settings panel: Cue base URL input + `browser.permissions.request()` call on save
- [ ] 5.3 Auth panel: login flow against the configured Cue instance, storing JWT in `browser.storage.local`
- [ ] 5.4 Document upload panel: file picker + multipart upload to the current session
- [ ] 5.5 Trigger button + active-page extraction → suggestion stream → write-back orchestration
- [ ] 5.6 Citation rendering: per-field collapsible note with source + position + excerpt
- [ ] 5.7 Audit-report download link wired to `GET /audit-report`
- [ ] 5.8 Log-out action that clears credentials from `browser.storage.local`
- [ ] 5.9 First-use privacy disclosure modal

## 6. Cue API `/extract-form` Endpoint

- [ ] 6.1 Add `POST /extract-form` route in `cue_api/api.py` (or `cue_api/routes/extract.py`)
- [ ] 6.2 Implement extraction helper (LLM prompt + JSON-mode parse) returning `BatchSuggestItem[]`
- [ ] 6.3 Wire JWT auth + session resolution through the existing middleware
- [ ] 6.4 Emit `EXTRACT_FORM` audit event via `m_shared/utils/audit.py`
- [ ] 6.5 Return `502` on LLM failure with a stable error code; `[]` on no fields detected
- [ ] 6.6 Unit tests: happy path, empty page text, malformed LLM JSON, auth failure
- [ ] 6.7 Integration test: end-to-end with a fixture HTML page

## 7. Extension-Origin CORS

- [ ] 7.1 Add `EXTENSION_ALLOWED_ORIGINS` env var to Cue API CORS configuration
- [ ] 7.2 Parse comma-separated origins; reject wildcards with a startup warning; exclude malformed entries
- [ ] 7.3 Allow credentialed requests from allowed extension origins
- [ ] 7.4 Document the variable in `.env.example` and `docs/DEPLOYMENT.md`
- [ ] 7.5 Unit tests: empty default rejects all extension origins, allowed origin accepted with credentialed headers, wildcard rejected at startup

## 8. End-to-End Validation

- [ ] 8.1 Manual test: known-good fixture form (in `cue_extension/test_data/`) — login → upload → trigger → fill → citations rendered
- [ ] 8.2 Manual test: live Google Form — extraction + write-back parity with fixture
- [ ] 8.3 Manual test: live Microsoft Form — extraction + write-back parity with fixture
- [ ] 8.4 Manual test: plain `<form>` page (gov-style) — semantic extractor handles it
- [ ] 8.5 Manual test: SPA-style form with no semantic markup — LLM-assisted tier invoked, items returned, write-back succeeds
- [ ] 8.6 Verify `EXTRACT_FORM` audit events appear in the session report

## 9. Distribution

- [ ] 9.1 Chrome Web Store unlisted listing — store assets (icons, screenshots, description, justification for `<all_urls>`)
- [ ] 9.2 Mozilla AMO unlisted listing — same assets, plus signed `.xpi`
- [ ] 9.3 Document install URLs in `docs/DEPLOYMENT.md`
- [ ] 9.4 Document optional enterprise force-install policy snippet (Chrome `ExtensionInstallForcelist`, Firefox `ExtensionSettings`)

## 10. Documentation

- [ ] 10.1 `cue_extension/README.md` — local install, build, structure overview
- [ ] 10.2 `docs/DEPLOYMENT.md` — extension section: install, CORS configuration, privacy posture
- [ ] 10.3 `docs/CUE_API.md` — document `POST /extract-form`
- [ ] 10.4 `docs/BROWSER_EXTENSION_PLAN.md` — note the spec has landed and link to the change directory

## 11. Tests and CI Hygiene

- [ ] 11.1 JS unit tests for extractors against snapshot HTML fixtures (Google Forms, MS Forms, semantic, SPA)
- [ ] 11.2 JS unit tests for write-back dispatcher per element kind
- [ ] 11.3 Cue API tests for `/extract-form` (unit + integration)
- [ ] 11.4 CORS tests for `EXTENSION_ALLOWED_ORIGINS`
- [ ] 11.5 CI: JS tests scoped to `cue_extension/`, Python tests unaffected; build artefacts uploaded for manual install

## 12. Spec Maintenance

- [ ] 12.1 After deployment, archive this change: `openspec archive add-cue-browser-extension --yes`
- [ ] 12.2 Confirm `cue-extension/spec.md` is materialised and `answer-suggestion` and `auth-security` deltas merge cleanly
