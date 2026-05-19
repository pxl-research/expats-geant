## 1. i18n Infrastructure

- [ ] 1.1 Create `m_shared/i18n.py` with `load_translations(directory)` and `t(lang, key, **kwargs)` function; English fallback on missing keys with logged warning
- [ ] 1.2 Create `shape_ui/i18n/en.json` with all ~120 translation keys extracted from templates, routes, and JS files
- [ ] 1.3 Register `t()` as a Jinja2 global in `shape_ui/router.py`, resolving language from the request's session style profile
- [ ] 1.4 Write unit tests for `m_shared/i18n.py`: key lookup, interpolation, fallback, missing key warning

## 2. API Error Codes

- [ ] 2.1 Define error code constants for Shape API errors (e.g. `session_not_found`, `file_too_large`, `oidc_not_configured`, `unsupported_file_type`)
- [ ] 2.2 Update `shape_api/routes/chat.py` error responses to include `{"code": "...", "message": "..."}`
- [ ] 2.3 Update `shape_api/routes/auth.py` error responses with codes
- [ ] 2.4 Update `shape_api/routes/tools.py` error responses with codes
- [ ] 2.5 Update `shape_api/routes/transforms.py` error responses with codes
- [ ] 2.6 Add error code translation keys to `en.json` (e.g. `error.session_not_found`)

## 3. Structured Validation Issues

- [ ] 3.1 Modify `shape_api/conversation.py` `execute_chat_turn()` to return validation issues as structured data instead of appending English text to the reply
- [ ] 3.2 Update `shape_api/routes/chat.py` chat endpoint to include `validation_issues` array in the response JSON
- [ ] 3.3 Add validation issue translation keys to `en.json` (e.g. `validation.scale_too_short`)
- [ ] 3.4 Update existing conversation tests to verify structured issues are returned separately from reply text

## 4. Template i18n (Shape UI)

- [ ] 4.1 Replace hardcoded strings in `base.html` with `{{ t(key) }}` calls
- [ ] 4.2 Replace hardcoded strings in `index.html`
- [ ] 4.3 Replace hardcoded strings in `setup.html`
- [ ] 4.4 Replace hardcoded strings in `chat.html`
- [ ] 4.5 Replace hardcoded strings in `export.html`
- [ ] 4.6 Replace hardcoded strings in `error.html`
- [ ] 4.7 Replace hardcoded strings in all partials (`partials/*.html`)

## 5. Python Route i18n (Shape UI)

- [ ] 5.1 Update `shape_ui/routes/workspace.py` error messages to use `t()`
- [ ] 5.2 Update `shape_ui/routes/setup.py` error messages to use `t()`
- [ ] 5.3 Update `shape_ui/routes/auth.py` error messages to use `t()`

## 6. JavaScript i18n

- [ ] 6.1 Inject `window.__i18n` translation object into `base.html` from the server
- [ ] 6.2 Update `chat.js` to reference `window.__i18n` for confirmation dialogs and status text
- [ ] 6.3 Update `export.js` to reference `window.__i18n` for button labels and feedback text

## 7. Chat UI: Render Structured Validation Issues

- [ ] 7.1 Update `chat.html` / `partials/message.html` to render `validation_issues` as translated, visually distinct notes below the assistant reply
- [ ] 7.2 Add CSS styling for validation issue notes (icon + muted colour to distinguish from LLM text)

## 8. Translation Files

- [ ] 8.1 Create `nl.json` (Dutch translations)
- [ ] 8.2 Create `fr.json` (French translations)
- [ ] 8.3 Create `de.json` (German translations)
- [ ] 8.4 Create `es.json` (Spanish translations)
- [ ] 8.5 Create `it.json` (Italian translations)
- [ ] 8.6 Create `pt.json` (Portuguese translations)
- [ ] 8.7 Flag domain-specific terms (survey methodology) for native speaker review

## 9. Testing and Validation

- [ ] 9.1 Write translation key consistency test: verify all language files have the same keys as `en.json`
- [ ] 9.2 Smoke-test Shape UI in at least 2 non-English languages (nl, fr) in the browser
- [ ] 9.3 Verify API error responses include both `code` and `message` fields
- [ ] 9.4 Verify chat responses return `validation_issues` as structured data
