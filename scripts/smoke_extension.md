# Cue Browser Extension — Smoke Checklist

A five-to-ten-minute manual run that proves the end-to-end loop works in real
Chrome before merging extension changes. Run this before merging any
extension change that touches extraction, write-back, or the auth/session
lifecycle.

The flow is deliberately manual; Chrome extension testing in Playwright is
painful and the maintenance cost dwarfs the benefit for a PoC.

---

## Pre-flight (one-time per environment)

- [ ] Cue services running: `docker compose ps` shows `cue-api` healthy on
      `http://localhost:8801`.
- [ ] Sanity probe: `curl -s http://localhost:8801/health` → `{"status":"healthy"}`.
- [ ] Extension bundle built: `(cd cue_extension && npm install && npm run build)`
      produces `cue_extension/dist/chrome/`.
- [ ] `cue_extension/dist/chrome/manifest.json` exists and lists
      `popup.html`, `content.js`, `sw.js`.

## 1. Load the unpacked extension in Chrome

- [ ] Open `chrome://extensions`, enable **Developer mode** (top-right toggle).
- [ ] Click **Load unpacked**, choose `cue_extension/dist/chrome/`.
- [ ] Copy the assigned **extension ID** (32-character hex string shown on the
      card; persistent per machine).
- [ ] Pin the extension to the toolbar.

## 2. Wire up CORS for the extension's origin

The Cue API rejects requests from any browser-extension origin not listed in
`EXTENSION_ALLOWED_ORIGINS`. Add yours and restart cue-api once.

- [ ] Add to `.env` at the repo root:
      `EXTENSION_ALLOWED_ORIGINS=chrome-extension://<extension-id>`
- [ ] `docker compose up -d cue-api` (re-creates the container with the new env).
- [ ] Verify in the cue-api logs:
      `docker compose logs cue-api | grep "allowing extension origins"` should
      print the configured origin.
- [ ] Preflight probe:
      ```
      curl -i -X OPTIONS http://localhost:8801/extract-form \
        -H "Origin: chrome-extension://<extension-id>" \
        -H "Access-Control-Request-Method: POST" 2>&1 | grep -i 'access-control-allow-origin'
      ```
      Should echo the same origin in the response header.

## 3. First-run popup + Cue URL + login

- [ ] Click the extension icon. The **first-use privacy modal** appears. Read,
      accept.
- [ ] In the onboarding panel, enter `http://localhost:8801` as the Cue URL.
- [ ] Click **Save & request permission**. Chrome shows a host-permission
      prompt for `http://localhost/*`. Allow it.
- [ ] Login panel appears. Enter:
      - User ID: any string (e.g. `smoke-test`)
      - API secret: matches `API_SECRET` from `.env` (read with
        `docker compose exec cue-api printenv API_SECRET`)
- [ ] Click **Log in**. The ready panel appears. The `Log out` button shows
      in the header.

## 4. Upload a source document

- [ ] In the **Source documents** section, choose any small PDF, DOCX, TXT, or
      MD file (e.g. `tests/test_data/documents/sample.txt`).
- [ ] Click **Upload**. The upload appears in the log with its byte count.

## 5. Extract — Tier 1: Google Forms

- [ ] In the same Chrome window, navigate to a public Google Form. (Any survey
      from a known public link works; or create a one-question form via
      `forms.google.com` to control the content.)
- [ ] Open the popup. Click **Analyse this page**.
- [ ] Status line should read: `Extractor: google-forms — N field(s). Streaming
      suggestions…`
- [ ] Each detected field gets a suggestion appended in the popup with a
      citation line beneath it (`<source> · <position>%: <excerpt>`).
- [ ] Each suggestion's value appears in the corresponding form field on the
      page (write-back).

## 6. Extract — Tier 2: Semantic HTML

- [ ] Open `tests/test_data/html_forms/simple_form.html` in Chrome via
      `file://` (drag onto a tab, or paste the full path into the address bar).
- [ ] Open the popup. Click **Analyse this page**.
- [ ] Status: `Extractor: semantic-html — 7 field(s).`
- [ ] Six form controls (text, email, radio, checkbox, select, range, textarea)
      should be populated; citations rendered for each.

## 7. Extract — Tier 3: LLM-assisted fallback

- [ ] Open `tests/test_data/html_forms/spa_form.html` via `file://`. (Plain
      `<div>`s, no `<label>`s — semantic-HTML returns zero items.)
- [ ] Open the popup. Click **Analyse this page**.
- [ ] Status: `Extractor: llm-fallback — N field(s).` (`N` ≥ 2 expected.)
- [ ] At least one form field should be written back. Some may be skipped if
      the label-text matching can't find a host element — that's expected; the
      popup still shows the suggestion + citation.

## 8. Audit-report check (PII posture)

- [ ] Click **Download audit report** in the popup. A JSON file downloads.
- [ ] Open it. Confirm:
      - `EXTRACT_FORM` events are present (one per LLM-fallback run).
      - Each `EXTRACT_FORM` entry's `details` has `url`, `item_count`, `model`
        — **and nothing else**.
      - `SUGGEST` events are present for each item.
      - The `page_text` you supplied is NOT in the report (grep the file with
        a unique substring from the page you analysed; expect zero hits).
      - The form-field VALUES written back to the page are NOT in the report.

## 9. Logout

- [ ] Click **Log out**. JWT cleared. Re-opening the popup shows the login
      panel again; the Cue URL is remembered.

---

## Firefox parity (Phase E)

Re-run sections 1, 3, 4, 5, 6, 7, 8 in Firefox 121+ (release channel or Nightly)
against the `firefox` bundle. Differences from the Chrome flow:

- [ ] Build: `(cd cue_extension && npm run build:firefox)` produces
      `cue_extension/dist/firefox/`.
- [ ] Load: `about:debugging#/runtime/this-firefox` → **Load Temporary
      Add-on…** → select `dist/firefox/manifest.json`. (Temporary add-ons are
      wiped on Firefox restart — re-load between sessions.)
- [ ] Extension ID is fixed by the manifest's `gecko.id`
      (`cue-form-filler@expat-geant.local`), not generated. Add
      `moz-extension://cue-form-filler@expat-geant.local` to
      `EXTENSION_ALLOWED_ORIGINS` in `.env`, then `docker compose up -d cue-api`.
- [ ] Preflight probe with the moz-extension origin returns the same echoed
      `access-control-allow-origin`:
      ```
      curl -i -X OPTIONS http://localhost:8801/extract-form \
        -H "Origin: moz-extension://cue-form-filler@expat-geant.local" \
        -H "Access-Control-Request-Method: POST" 2>&1 | grep -i 'access-control-allow-origin'
      ```
- [ ] Host-permission prompt copy differs from Chrome's, but the grant flow is
      identical. Allow it for `http://localhost/*`.
- [ ] Repeat extraction tiers 1/2/3 — extractor names and field counts must
      match Chrome's output exactly.
- [ ] Audit report contents must match Chrome's PII posture (URL + item_count
      + model only on `EXTRACT_FORM` entries).

Any user-visible divergence is a bug, not a documented difference; log it and
fix before declaring Phase E complete.

---

## Quick server-side sanity (no browser required)

If the browser flow fails, isolate whether the issue is server-side or
extension-side:

```bash
SECRET=$(docker compose exec -T cue-api printenv API_SECRET | tr -d '\r')
TOKEN=$(curl -s -X POST http://localhost:8801/auth/token \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"sanity\",\"api_secret\":\"$SECRET\"}" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')

curl -s -X POST http://localhost:8801/extract-form \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://example.test","page_text":"What is your name? What is your email?"}'

curl -s -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8801/audit-report?format=json' \
  | python3 -m json.tool | grep -A 5 EXTRACT_FORM
```

The first call should return an array of `BatchSuggestItem` entries (~2 items
for that prompt). The second should show an `EXTRACT_FORM` audit entry with
`{url, item_count, model}` only.
