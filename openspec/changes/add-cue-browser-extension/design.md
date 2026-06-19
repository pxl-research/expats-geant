## Context

Cue's existing respondent frontend (`cue_ui/`) requires the questionnaire to be
ingested via `POST /surveys/import` before answers can be drafted. This works
for institutional surveys but excludes the long tail of forms users encounter
in the browser — Google Forms, MS Forms, government portals, internal HR tools.

A standalone Firefox-only prototype already exists at
`pxl-research/tai-llm-ff-ext` ("Pixie Lite", MV2, v1.0.0). It demonstrates that
DOM scraping and write-back work in practice but talks directly to OpenRouter
with a pasted API key — no RAG, no citations, no audit trail, no
institutional posture. Pixie Lite remains as a lightweight "paste-an-API-key"
demo; this change builds its institutional sibling.

The Cue extension rebuilds that prototype as a first-class Cue frontend: MV3
(Chrome + Edge + Firefox from one source), Cue API as the backend, full
session lifecycle, evidence-backed answers with citations. Reusable pieces
from Pixie Lite (DOM addressing, per-tag write-back dispatch, popup shell,
font/CSS bundle) are forked once at the start; the two codebases do not stay
in sync.

## Goals / Non-Goals

**Goals:**

- Reach forms that live outside Cue's own ingestion path
- Reuse the existing Cue API (`/suggest/stream`, `/suggest/batch`) without
  reshaping the wire contract
- Per-platform extractors for the highest-volume targets (Google Forms,
  Microsoft Forms) with a deterministic semantic-HTML floor and an LLM-assisted
  fallback for unknown forms
- A single MV3 codebase that targets Chrome, Edge, and Firefox
- Privacy posture compatible with the institutional pilot — user-triggered
  only, explicit consent, no proactive scraping, configurable per-deployment
  CORS allow-list
- The extension owns the full session lifecycle (login, document upload,
  trigger, fill) so it works standalone

**Non-Goals:**

- Safari support — deferred until pilot feedback shows demand. Cost (~$300/yr +
  Mac + Xcode + App Store cycles) does not pencil for the PoC.
- Consuming an existing `cue_ui/` session JWT — full lifecycle only in v1.
- Replacing `cue_ui/` — the extension is a third frontend, not a successor.
- Background or proactive form analysis — user-triggered only.
- Reusing the Python adapter contract (`SurveyAdapter`) — the extension
  consumes a live DOM, not a versioned file format; the contracts diverge.
- Multi-page / SPA pagination handling beyond what each platform extractor
  requires for its own target.
- Typeform / JotForm / SurveyMonkey-respondent-UI extractors. Tier 2 work,
  post-PoC.

## Decisions

### Adapter pattern for form extraction, with `detect()` self-identification

**Decision:** Each extractor is a self-contained module exposing
`detect(url, document) → boolean` and `extract(document) → BatchSuggestItem[]`.
A registry iterates extractors in priority order and uses the first whose
`detect()` returns true. Extractors live one-per-file under
`cue_extension/src/extractors/`.

**Alternatives considered:**

- *Key-based dispatch (mirroring `m_shared/adapters/registry.py`)*: works for
  file-format conversion where the caller already knows the format. Doesn't
  work here — the extension cannot know in advance which platform a page
  belongs to.
- *One generic scraper with platform-specific branches inline*: matches
  Pixie Lite's structure. Grows fragile fast as more platforms are added; loses
  the symmetry with the server-side adapter layer.
- *Server-side extraction only (extension just sends raw HTML)*: shifts all
  work to the LLM, costs tokens on every call, removes the latency win of
  deterministic extraction on known platforms.

**Rationale:** `detect()` keeps each extractor independent and easy to reason
about. The registry stays tiny. Adding a new platform is one new file plus one
line in the registry. The shape mirrors `m_shared/adapters/` enough that
reviewers will recognise the pattern without it being a literal port.

### Three-tier extraction strategy

**Decision:** Extraction proceeds in three tiers, in order:

1. **Known-platform extractor** — Google Forms, MS Forms. Deterministic, zero
   LLM cost, fast.
2. **Semantic HTML extractor** — walks `<label>`/`<input>`/`<select>`/
   `<textarea>` for plain `<form>` elements. Deterministic, zero LLM cost.
   Covers gov forms, contact forms, the long tail of well-formed HTML.
3. **LLM-assisted extractor** — calls `POST /extract-form` with page text +
   URL when the previous tiers cannot extract any items. Costs tokens; audited
   like any other Cue call.

**Alternatives considered:**

- *Two-tier (known platform → LLM)*: drops the semantic-HTML floor. Plain
  contact-form pages and many government forms have perfectly clean
  `<label>`/`<input>` structure; sending them to the LLM wastes tokens and
  introduces variability.
- *Always-on LLM extraction*: simpler code, prohibitive cost on the pilot's
  expected query volume, and unnecessary latency on platforms with stable
  DOM signatures.

**Rationale:** Each tier handles a meaningfully different class of page.
Skipping the middle tier sacrifices the most common deterministic case.

### Extension owns the full session lifecycle

**Decision:** The popup handles login to the configured Cue instance,
document upload, session start, form filling, and audit-report download. No
dependency on `cue_ui/`.

**Alternatives considered:**

- *Consume an existing `cue_ui/` session JWT (paste or paired login)*: ships
  faster but makes the extension a satellite of `cue_ui/`. Users juggle two
  tools, and the institutional pilot loses the "install the extension, point it
  at your Cue, done" story.

**Rationale:** Users who want the extension want it because they do not have
the form pre-ingested in Cue. Requiring them to first visit `cue_ui/` to start
a session defeats the use case. The full-lifecycle popup is a larger build but
matches the actual user journey.

### Streaming as the default delivery mode

**Decision:** The extension consumes `POST /suggest/stream` by default. Each
field populates as its answer lands. `POST /suggest/batch` remains the fallback
for environments where SSE is blocked.

**Rationale:** A 20-field form would otherwise spin a single progress bar for
30+ seconds. Per-item streaming matches the popup's existing entry-at-a-time
render and gives the user something to look at immediately. The plan doc
already settled this; recorded here for completeness.

### MV3 baseline, single codebase, per-host permissions via `optional_host_permissions`

**Decision:** Target MV3 from day one. Ship `host_permissions: ["<all_urls>"]`
for the content script (functionally required — the user picks which page to
analyse). Ship **no** Cue API host grants by default; the popup calls
`browser.permissions.request()` with the operator-entered Cue URL.

**Alternatives considered:**

- *MV2*: Firefox-only, going away on Chrome.
- *Hardcode the Cue host*: each institution runs its own Cue. Not viable.
- *`<all_urls>` for the API too*: excessive, slows store review, raises pilot
  questions.

**Rationale:** MV3 is stable on Firefox since v109 (Jan 2023) and is mandatory
on Chrome (MV2 removed June 2024). Manifest differences between Chromium and
Firefox reduce to `browser_specific_settings.gecko.id` (ignored by Chrome) and
the `browser.*` shim. The `optional_host_permissions` pattern is the cleanest
answer to the "every institution has its own host" problem — the extension
ships with no API host grants, the user enters their Cue URL in settings, and
the extension calls `browser.permissions.request()` to grant just that origin.
This is the smallest target for store reviewers. The content script's
`<all_urls>` grant remains in `host_permissions` because it is functionally
required: the user picks which page to analyse, and the extension cannot know
the host set in advance.

### CORS allow-list with no default extension origins

**Decision:** Cue API CORS configuration accepts a comma-separated list of
extension origins (`chrome-extension://<id>`, `moz-extension://<uuid>`) via
environment variable. Defaults to empty — operators opt in explicitly per
deployment.

**Alternatives considered:**

- *Allow all `chrome-extension://*` origins*: easy to misconfigure into a
  cross-origin leak surface.
- *Hardcode the published extension IDs*: forces a rebuild of Cue every time
  the extension ID changes (development, unlisted listings, enterprise rebuilds).

**Rationale:** Operator-controlled allow-list is the standard CORS posture and
gives each deployment freedom to pin the exact extension build their pilot is
distributing.

### JWT in extension storage, no API-key fallback

**Decision:** Authentication uses the existing `POST /auth/token` flow. The
popup logs the user in, obtains a JWT, and stores it in
`browser.storage.local`. Pixie Lite's API-key-in-localStorage model is
explicitly not carried over.

**Rationale:** Pixie Lite's posture is unacceptable for an institutional pilot
under GDPR scrutiny. Reusing `/auth/token` (already specified in
`auth-security`) means the extension fits inside the existing identity model
with no new surface area.

### Repo placement: `cue_extension/` sibling under monorepo

**Decision:** New `cue_extension/` directory alongside `cue_api/`, `cue_ui/`,
`shape_api/`, `shape_ui/`. Not a separate repo.

**Rationale:** The extension talks to Cue exclusively, ships against Cue's
API version, and shares its release cadence and governance. It is
functionally the third Cue frontend; same contributors, same licence.
Cross-repo sync would be tax with no benefit. The tooling difference
(JS/TypeScript vs Python) is contained by scoping CI jobs per package; the
store-review release path is independent of `docker-compose up` for the
backend services and that separation is healthy.

## Risks / Trade-offs

- **JS-heavy forms (React, Vue, Shadow DOM, framework validation)**: most
  fragile surface. Per-platform extractors handle Google Forms / MS Forms;
  semantic HTML handles plain `<form>` elements; the LLM fallback handles the
  rest. Risk: write-back into React-controlled inputs needs
  `nativeInputValueSetter` plumbing (mitigation: reuse Pixie Lite's dispatch
  code as the starting point and budget time for refinement).
- **Store review of `<all_urls>` content-script grant**: AMO and CWS reviewers
  will ask why the extension needs broad host access. Mitigation: explicit
  justification in the store listing ("fills forms on any page the user
  triggers"); no background scraping; user-triggered only.
- **Extractor drift**: platforms update their DOM. Google Forms in particular
  rotates class names regularly. Mitigation: extractors target stable selectors
  (`[role="listitem"]`, `data-params`) rather than CSS class names; semantic
  HTML and LLM fallbacks catch breakage; CI smoke-test against snapshot HTML
  fixtures so regressions surface before users see them.
- **LLM extractor cost**: `POST /extract-form` is the most expensive tier per
  call. Mitigation: only invoked when the deterministic tiers find zero items;
  audited via the same audit-compliance trail as suggestions.
- **CORS misconfiguration**: an over-permissive allow-list could let other
  extensions hit a pilot Cue instance. Mitigation: defaults to empty list and
  documents the per-deployment opt-in step in `docs/DEPLOYMENT.md`.
- **Cross-browser maintenance**: Chrome and Firefox MV3 behave differently in
  small ways (`browser_specific_settings.gecko.id`, slight permissions UX
  differences). Mitigation: `webextension-polyfill` plus a per-browser build
  matrix; consider WXT if the codebase outgrows ad-hoc tooling.

## Migration Plan

- **No data migration**: this is a new component; nothing exists to migrate.
- **Rollout**:
  1. Land the extension scaffold + Google Forms extractor + semantic HTML
     fallback + popup with full lifecycle. Validate end-to-end against a known
     Google Form.
  2. Add the MS Forms extractor. Validate against a known MS Form.
  3. Add the `POST /extract-form` endpoint and wire the LLM fallback.
  4. CWS unlisted + AMO unlisted listings; document install URLs in
     `docs/DEPLOYMENT.md`.
  5. Roll out to pilot institutions; collect field-detection accuracy and
     citation-usefulness feedback.
- **Rollback**: the extension is a separately distributed artifact. If the
  pilot reveals fundamental issues, operators can revoke the CORS allow-list
  entry to lock the extension out without affecting `cue_ui/` users.

## Open Questions

- **Citation rendering in the popup**: the plan doc lists this as undecided.
  Default proposal: each filled field gets a collapsible note below it showing
  source + line range, plus a "Sources" panel summarising all citations. Needs
  a small design pass during implementation; not a blocker for the proposal.
- **LLM-extractor confidence threshold**: how does the extension know the
  semantic-HTML tier has "failed" enough to warrant the LLM tier? Default
  proposal: zero extracted items triggers LLM fallback. Alternative: low-
  confidence flag from the semantic extractor when too few labels were
  resolved.
- **Build tooling**: ad-hoc shell scripts for the spike, then WXT or Plasmo if
  the codebase grows? Defer until the spike de-risks the approach; the choice
  doesn't affect the spec.
- **Audit-report consumption**: the popup can offer "download audit report"
  after a session, reusing the existing `GET /audit-report` endpoint. Confirm
  during implementation that the existing report covers extension-originated
  sessions without spec changes.
