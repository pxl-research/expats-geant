## Context

The Shape UI is a server-rendered FastAPI app (Jinja2 + HTMX). Users select a survey
language during style setup; this language is persisted in the session's style profile.
The LLM already responds in the selected language (Phase 1 fix in `shape_api/style.py`).
This change extends language support to the UI chrome and API error handling.

The project has 7 supported languages: en, nl, fr, de, es, it, pt.

## Goals / Non-Goals

**Goals:**
- All user-visible UI text in Shape UI is translatable
- API errors carry stable codes that frontends can translate independently
- Validation issues from the chat flow are structured data, not injected English text
- The i18n module is reusable by Cue UI in a future effort
- Translation files are simple to maintain and review

**Non-Goals:**
- Full gettext/Babel toolchain (overkill for ~120 strings in a PoC)
- Runtime language switching without page reload
- Translating LLM system prompts (internal, not user-facing)
- Translating API response messages (API stays English)
- Cue UI i18n (separate future change)
- Right-to-left (RTL) layout support

## Decisions

### JSON-based translation over Babel/gettext

**Decision:** Use plain JSON files (one per language) loaded at startup, with a simple
`t(lang, key, **kwargs)` Python function.

**Alternatives considered:**
- *Babel + gettext (.po/.mo)*: Industry standard, excellent tooling, but requires a
  compile step, introduces a new dependency, and the `.po` format is less readable for
  quick edits. Overkill for ~120 strings.
- *python-i18n*: Lightweight wrapper, but adds a dependency for minimal benefit over
  a 30-line custom loader.

**Rationale:** JSON is readable, diffable, needs no build step, and the string count
is small enough that a flat key-value file per language is manageable. The helper
module (`m_shared/i18n.py`) is <50 lines. If the project outgrows this approach,
migrating keys to `.po` files is straightforward.

### UI language follows style profile

**Decision:** The UI language is determined by the session's `style_profile.language`
value. There is no separate UI language selector.

**Rationale:** Adding a second language setting creates UX confusion ("which language
controls what?"). The survey language and UI language should match for non-English
users. For unauthenticated pages (login, error), English is used as the fallback.

### API stays English, adds error codes

**Decision:** API error responses keep their English `message` field and gain a stable
`code` field (e.g. `"session_not_found"`). The UI translates based on the code.

**Alternatives considered:**
- *Translate API messages server-side*: Requires threading language context through
  every API endpoint, couples the API to UI concerns, and breaks third-party consumers
  who expect English.

**Rationale:** Error codes are a stable contract. The English message serves developers
and API consumers. The UI is the right layer to present localised text.

### Structured validation issues in chat response

**Decision:** The chat endpoint returns validation issues as a separate structured field
(`validation_issues`) alongside the reply text, instead of appending English text like
"I also noticed: {message} -- was this intentional?" to the LLM response.

**Rationale:** Injecting English text into a Dutch/French LLM response breaks language
consistency. Structured data lets the UI render and translate validation notes in the
correct language, and gives the frontend control over presentation.

### JavaScript translations via server-injected object

**Decision:** The server injects a `window.__i18n` object into the base template
containing the translations for the current language. JS code references keys from
this object.

**Alternatives considered:**
- *Fetch translations via API call*: Extra round-trip, adds complexity.
- *Inline each string in data attributes*: Scattered, hard to maintain.

**Rationale:** The JS string count is small (~5). A single injected object keeps
translations centralised and avoids extra network requests.

## Risks / Trade-offs

- **Translation quality**: Initial translations can be LLM-generated, but should be
  reviewed by native speakers before the TNC demo. Risk: mistranslations in specialised
  survey methodology terms.
  Mitigation: Keep strings short and generic; flag domain-specific terms for review.

- **Missing translations at runtime**: If a key is missing from a language file, the
  system falls back to English. This is acceptable for a PoC but should log a warning
  so missing keys are caught during development.

- **String count growth**: As features are added, new strings must be added to all 7
  JSON files. Risk: translations drift out of sync.
  Mitigation: A simple CI check (or test) can verify all language files have the same
  keys as `en.json`.

## Open Questions

- Should pluralisation be handled (e.g. "1 question" vs "5 questions")? Proposal:
  use simple `{count}` interpolation with separate keys for singular/plural where
  needed (e.g. `questions_count_one`, `questions_count_other`). Full CLDR plural
  rules are out of scope.
