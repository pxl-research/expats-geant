## 0. Prerequisites
- [ ] 0.1 `refactor-questionnaire-adapters` implemented and merged (adapter capability discovery
          and `submit_responses()` required)

## 1. Spec
- [x] 1.1 Add `survey-ui` capability spec

## 2. Module Scaffold
- [ ] 2.1 Create `m_ui/` package with `main.py`, `router.py`, `api_client.py`
- [ ] 2.2 Add `m_ui/requirements.txt` (fastapi, jinja2, httpx, python-multipart)
- [ ] 2.3 Add `m_ui/Dockerfile` and register as `ui` service in `docker-compose.yml`
- [ ] 2.4 Set `AUTOFILL_API_URL` env var in compose for UI → API communication

## 3. API Client
- [ ] 3.1 Implement `api_client.get_survey(survey_id)` → Survey dict
- [ ] 3.2 Implement `api_client.get_capabilities(format)` → set[str]
- [ ] 3.3 Implement `api_client.batch_suggest(survey_id, session_id)` → suggestions list
- [ ] 3.4 Implement `api_client.submit_responses(survey_id, session_id, responses)` → None
- [ ] 3.5 Implement `api_client.import_survey_file(file_bytes, format)` → survey_id

## 4. Templates
- [ ] 4.1 Create `base.html` (layout, static asset links)
- [ ] 4.2 Create `upload.html` — file upload form (file picker + format selector + display-only notice)
- [ ] 4.3 Create `survey.html` — renders survey form with question controls per type:
          single_choice (radio), multiple_choice (checkboxes), open_ended (textarea),
          slider (range input), ranking (reorderable list)
- [ ] 4.4 Add inline suggestion block per question (suggestion text, reasoning, citations)
- [ ] 4.5 Add accept / edit / dismiss controls per suggestion
- [ ] 4.6 Implement `review-state.js` — localStorage helper: read/write `review-{session_id}`
          JSON map; called on every accept/edit/dismiss; no server round-trip
- [ ] 4.7 Restore saved review state on page load from localStorage (pre-fill accepted values,
          hide dismissed suggestion blocks)
- [ ] 4.8 Add conditional submit button (rendered only if `"submit"` in capabilities)
- [ ] 4.9 Add display-only banner (rendered when `"submit"` NOT in capabilities)
- [ ] 4.10 Create `submitted.html` (success confirmation page; clears localStorage for session)
- [ ] 4.11 Add error state to `survey.html` (inline error on submission failure, answers preserved)
- [ ] 4.12 Add session-expiry page for resume-after-TTL case (discard local state, offer restart)

## 5. Routes
- [ ] 5.1 `GET /` — landing page with options: enter survey ID or upload file
- [ ] 5.2 `POST /upload` — accept file + format, call import API, redirect to session review URL
- [ ] 5.3 `GET /session/{session_id}/review` — load survey + capabilities + saved review state,
          render survey.html
- [ ] 5.4 `GET /session/{session_id}/suggest` (HTMX partial) — fetch and inject suggestion blocks
- [ ] 5.5 `POST /session/{session_id}/submit` — collect form data, call submit API, redirect to
          submitted.html or return error partial

## 6. Tests
- [ ] 6.1 Unit test `api_client` methods with mocked HTTP responses (including import_file,
          get_review_state, save_review_state)
- [ ] 6.2 Integration test: render survey page for a known survey fixture
- [ ] 6.3 Integration test: submit flow with a mock adapter (LimeSurvey fixture)
- [ ] 6.4 Test display-only mode renders banner and no submit button
- [ ] 6.5 Test file upload flow → display-only session created → banner shown
- [ ] 6.6 Test review state auto-save: accept action → localStorage written correctly
- [ ] 6.7 Test resume: localStorage populated → page load → accepted values pre-filled,
          dismissed suggestions hidden
- [ ] 6.8 Test expired session resume → API returns 404/410 → expiry message shown,
          localStorage cleared
- [ ] 6.9 Test cleared localStorage → all questions render in pending state, no error shown
