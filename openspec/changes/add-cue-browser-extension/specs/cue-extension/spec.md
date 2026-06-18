## ADDED Requirements

### Requirement: Manifest V3 Cross-Browser Baseline

The extension SHALL ship a Manifest V3 bundle that loads in Chrome, Edge, and
Firefox from a single source. The manifest SHALL include
`browser_specific_settings.gecko.id` for Firefox while remaining valid for
Chromium-based browsers. The extension SHALL use `webextension-polyfill` (or
equivalent shim) so a single `browser.*` API surface works across all
supported browsers. Safari SHALL NOT be a target in this version.

#### Scenario: Single source bundles for all supported browsers

- **WHEN** the build pipeline runs
- **THEN** browser-specific bundles are produced from one source tree
- **AND** each bundle loads in its target browser without manifest errors

#### Scenario: Firefox-specific manifest fields ignored on Chromium

- **WHEN** the same manifest is loaded by Chrome or Edge
- **THEN** `browser_specific_settings.gecko.id` is ignored
- **AND** the manifest passes Chrome's validation

#### Scenario: Safari not targeted

- **WHEN** the build pipeline runs
- **THEN** no Safari-specific artefact is produced
- **AND** Safari is documented as out of scope for this release

### Requirement: Three-Tier Form Extraction

The extension SHALL extract form items in three tiers, in order: (1) known-
platform extractors, (2) a semantic HTML extractor, (3) an LLM-assisted
extractor calling `POST /extract-form`. A tier SHALL be invoked only when all
preceding tiers either did not match the page or returned zero items. The
output of every tier SHALL conform to the `BatchSuggestItem` DTO already
defined for `POST /suggest/batch` and `POST /suggest/stream`.

#### Scenario: Known platform recognised

- **WHEN** the user triggers extraction on a page a known-platform extractor
  matches
- **THEN** that extractor produces `BatchSuggestItem[]`
- **AND** the semantic and LLM tiers are not invoked

#### Scenario: Fallback to semantic HTML

- **WHEN** no known-platform extractor matches
- **THEN** the semantic HTML extractor walks `<form>` and form-control elements
- **AND** the LLM tier is not invoked unless the semantic tier returns zero
  items

#### Scenario: LLM-assisted last resort

- **WHEN** the semantic HTML extractor returns zero items
- **THEN** the extension calls `POST /extract-form` with the page text and URL
- **AND** the returned `BatchSuggestItem[]` is used for the suggestion request

#### Scenario: All tiers fail

- **WHEN** no tier produces any items
- **THEN** the popup shows a clear "no form fields detected" message
- **AND** no suggestion request is made

### Requirement: Extractor Registry with detect() Self-Identification

The extension SHALL maintain an extractor registry where each extractor module
exposes a `detect(url, document) → boolean` function and an
`extract(document) → BatchSuggestItem[]` function. The registry SHALL iterate
extractors in declared priority order and select the first whose `detect()`
returns true. Each extractor SHALL live in its own file under
`cue_extension/src/extractors/`.

#### Scenario: Priority order respected

- **WHEN** a page matches multiple extractors
- **THEN** the registry selects the first match in declared priority order

#### Scenario: One extractor per file

- **WHEN** the extractor directory is inspected
- **THEN** each platform-specific extractor occupies its own file
- **AND** the semantic HTML fallback occupies its own file
- **AND** the LLM-assisted extractor occupies its own file

#### Scenario: New extractor pluggable

- **WHEN** a new extractor file is added to the registry
- **THEN** no changes to existing extractors are required
- **AND** the registry routes matching pages to it on the next build

### Requirement: Google Forms Extractor

The extension SHALL provide a Google Forms extractor that activates on
`docs.google.com/forms/*` URLs. The extractor SHALL identify questions via the
`[role="listitem"]` container and translate them to `BatchSuggestItem` entries
mapping `input[type="text"]`, `textarea`, radio groups, checkbox groups,
`select`, and range inputs as documented in
`docs/BROWSER_EXTENSION_PLAN.md`.

#### Scenario: Open-ended question mapped

- **WHEN** a Google Forms question renders a text or paragraph input
- **THEN** it is emitted as `type: "open_ended"`

#### Scenario: Single-choice mapped with choices

- **WHEN** a Google Forms question renders a radio group
- **THEN** it is emitted as `type: "single_choice"` with the choice labels

#### Scenario: Multiple-choice mapped with choices

- **WHEN** a Google Forms question renders a checkbox group
- **THEN** it is emitted as `type: "multiple_choice"` with the choice labels

#### Scenario: Detection rejects unrelated Google pages

- **WHEN** the active page is a Google Doc, Sheet, or non-Forms URL on
  `docs.google.com`
- **THEN** the extractor's `detect()` returns false

### Requirement: Microsoft Forms Extractor

The extension SHALL provide a Microsoft Forms extractor that activates on
`forms.office.com` and `forms.cloud.microsoft` URLs. The extractor SHALL
identify questions via stable `data-automation-id` selectors and translate
them to `BatchSuggestItem` entries using the same DTO mapping as the Google
Forms extractor.

#### Scenario: Detection on either Microsoft Forms host

- **WHEN** the active page is hosted on `forms.office.com` or
  `forms.cloud.microsoft`
- **THEN** the extractor's `detect()` returns true

#### Scenario: Question text resolved from accessibility metadata

- **WHEN** a Microsoft Forms question is rendered
- **THEN** the extractor resolves the prompt text from the nearest label,
  `aria-label`, or `aria-describedby` reference

### Requirement: Semantic HTML Extractor

The extension SHALL provide a semantic HTML extractor that walks `<form>`
elements and form controls (`input`, `textarea`, `select`) on any page. This
extractor SHALL be the last deterministic tier — invoked only when no known-
platform extractor matches. Prompt text SHALL be resolved from associated
`<label for="...">`, parent `<label>`, `aria-label`, `aria-labelledby`,
`placeholder`, or nearest preceding text node, in that order.

#### Scenario: Plain form on an unknown site

- **WHEN** the active page has a `<form>` with labelled inputs but no
  known-platform extractor matches
- **THEN** the semantic extractor produces `BatchSuggestItem[]`

#### Scenario: Label resolution order

- **WHEN** an input has both an associated `<label>` and a `placeholder`
- **THEN** the label text is preferred for the prompt
- **AND** the placeholder is used only if no label is present

#### Scenario: Hidden and disabled controls skipped

- **WHEN** form controls are `hidden`, `disabled`, or `type="hidden"`
- **THEN** they are not emitted as `BatchSuggestItem` entries

### Requirement: LLM-Assisted Extractor (Third Tier)

The extension SHALL provide an LLM-assisted extractor that calls the Cue API's
`POST /extract-form` endpoint with the active page's text content and URL.
This tier SHALL be invoked only when the semantic HTML extractor returns zero
items. The returned `BatchSuggestItem[]` SHALL be used for the subsequent
suggestion request without further extension-side reshaping.

#### Scenario: LLM tier invoked on extraction miss

- **WHEN** the semantic HTML extractor returns zero items
- **THEN** the extension calls `POST /extract-form` with page text and URL
- **AND** the returned items are forwarded to `POST /suggest/stream`

#### Scenario: LLM tier disabled by setting

- **WHEN** the operator-controlled setting disables the LLM tier
- **THEN** the extension shows "no form fields detected" instead of calling
  `/extract-form`
- **AND** no LLM tokens are spent

### Requirement: Popup Owns Full Session Lifecycle

The extension's popup SHALL handle the complete Cue session lifecycle:
authentication against the configured Cue instance, document upload to the
session, session start, form-fill trigger, citation rendering, and optional
audit-report download. The extension SHALL NOT depend on `cue_ui/` for any
step in this lifecycle. Pasting an existing `cue_ui/` session JWT SHALL NOT
be supported in this release.

#### Scenario: First-time onboarding

- **WHEN** the popup opens with no stored configuration
- **THEN** it prompts for the Cue instance URL
- **AND** it prompts for authentication

#### Scenario: Documents uploaded from popup

- **WHEN** the user uploads source documents via the popup
- **THEN** the uploads target the active session via the existing Cue upload
  endpoint
- **AND** the documents become available for retrieval in subsequent suggestion
  calls

#### Scenario: Citations rendered after fill

- **WHEN** the suggestion stream completes
- **THEN** the popup displays each filled field with its citation metadata
  (source name, position, excerpt)

#### Scenario: No cue_ui dependency

- **WHEN** the user has never visited `cue_ui/`
- **THEN** the extension functions end-to-end without it

### Requirement: User-Triggered Operation Only

The extension SHALL only inspect or modify the active page in response to an
explicit user action — clicking the trigger button in the popup. The content
script SHALL NOT scrape, fingerprint, or observe pages in the background.

#### Scenario: No background scraping

- **WHEN** the user opens a page with form fields but does not click the
  trigger
- **THEN** the extension performs no DOM read of the page
- **AND** no network request is made to the Cue API or any other endpoint

#### Scenario: Explicit click required for fill

- **WHEN** the user clicks the trigger button
- **THEN** the content script reads the active page's DOM
- **AND** the extracted items are sent to the configured Cue instance

### Requirement: Streaming Suggestion Delivery by Default

The extension SHALL consume `POST /suggest/stream` as the default delivery
mode. Each field SHALL render its suggestion and citations into the popup as
that field's suggestion event arrives. `POST /suggest/batch` SHALL be
available as a fallback for environments where Server-Sent Events are blocked.

#### Scenario: Stream populates fields incrementally

- **WHEN** the extension calls `POST /suggest/stream`
- **THEN** each `event: suggestion` updates one field in the popup as it
  arrives
- **AND** the user sees progress without waiting for the full set

#### Scenario: Batch fallback on SSE failure

- **WHEN** the SSE connection cannot be established or is closed by an
  intermediary before completion
- **THEN** the extension falls back to `POST /suggest/batch`

### Requirement: DOM Write-Back Dispatcher

The extension SHALL write each suggested answer back into its originating DOM
element using a dispatcher keyed by element type. The dispatcher SHALL support
`input[type="text"]`, `input[type="email"]`, `input[type="number"]`,
`input[type="radio"]`, `input[type="checkbox"]`, `input[type="range"]`,
`textarea`, `select`, and rich-text editors (Quill, contenteditable) at
minimum. Framework-controlled inputs (React, Vue) SHALL receive synthetic
events that the framework's state layer observes (e.g.
`nativeInputValueSetter` + `input` event dispatch for React).

#### Scenario: Plain input populated

- **WHEN** a suggestion targets a plain `<input type="text">`
- **THEN** the dispatcher sets the value and dispatches an `input` event

#### Scenario: Radio group selection

- **WHEN** a suggestion targets a radio group
- **THEN** the dispatcher clicks the option matching the selected choice ID

#### Scenario: React-controlled input

- **WHEN** a suggestion targets a React-controlled input
- **THEN** the dispatcher uses `nativeInputValueSetter` to update the value
- **AND** dispatches an `input` event that React's onChange handler observes

### Requirement: Per-Host Cue API Permissions

The extension's manifest SHALL declare no Cue API host grants by default. The
popup SHALL request the operator-entered Cue origin at runtime via
`browser.permissions.request()` using `optional_host_permissions`. The
content script's `<all_urls>` host permission SHALL remain in
`host_permissions` because it is functionally required for scraping arbitrary
pages.

#### Scenario: New Cue URL prompts permission request

- **WHEN** the user enters a new Cue base URL in settings
- **THEN** the popup calls `browser.permissions.request()` for that origin
- **AND** rejects the URL change if the user denies the prompt

#### Scenario: Existing Cue URL reused without prompt

- **WHEN** the user re-opens the popup with a previously granted Cue URL
- **THEN** no new permission prompt is shown

### Requirement: Credential Storage

The extension SHALL store the Cue base URL and authentication token (JWT) in
`browser.storage.local`. The extension SHALL NOT use pasted API keys against
external LLM providers. The Cue base URL and JWT SHALL be cleared when the
user explicitly logs out from the popup.

#### Scenario: Credentials persist across browser restarts

- **WHEN** the browser is restarted
- **THEN** the popup remembers the configured Cue URL and active session

#### Scenario: Logout clears credentials

- **WHEN** the user clicks "log out" in the popup
- **THEN** the stored JWT is cleared from `browser.storage.local`
- **AND** subsequent triggers require re-authentication

### Requirement: Privacy Posture

The extension SHALL document its data-handling posture in the popup and in
`docs/DEPLOYMENT.md`: page content is read only on explicit user trigger; only
extracted form items (not full page HTML) are sent to the configured Cue
instance, except when the LLM-assisted tier is invoked; uploaded documents are
subject to Cue's existing session TTL; no third-party endpoint is contacted.

#### Scenario: First-use disclosure

- **WHEN** the popup is opened for the first time
- **THEN** a privacy disclosure is shown summarising what data is sent where

#### Scenario: Only extracted items leave the browser

- **WHEN** a known-platform or semantic extractor handles the page
- **THEN** only the resulting `BatchSuggestItem[]` is sent to the Cue instance
- **AND** full page HTML is never transmitted

#### Scenario: LLM tier transmission disclosed

- **WHEN** the LLM-assisted extractor is invoked
- **THEN** the popup discloses that the page's text content is being sent to
  the Cue instance for extraction
