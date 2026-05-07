## 1. Review State API

- [x] 1.1 Create `cue_api/routes/review_state.py` with `PUT /review-state/{question_id}` and `GET /review-state` endpoints
- [x] 1.2 Add request/response models to `cue_api/models.py`: `ReviewStateUpdate` (state, value, selected_id, selected_ids) and `ReviewStateResponse` (dict mapping question_id to state)
- [x] 1.3 Implement file I/O: read/write `review_state.json` in the session directory with thread-safe locking (same pattern as answer_report)
- [x] 1.4 Register the router in `cue_api/api.py`
- [x] 1.5 Write unit tests: save state, load state, overwrite state, empty session, session cleanup deletes file

## 2. Cue UI: Dual-Write Review State

- [x] 2.1 Update `review-state.js` to PUT state to the API alongside localStorage writes (fire-and-forget fetch call)
- [x] 2.2 Update `cue_ui/routes/review.py` to fetch server-side review state on page load and pass it to the template
- [x] 2.3 Update `survey.html` to inject server-side state as inline JSON for the JS to pick up
- [x] 2.4 Update `review-state.js` load logic: prefer server state over localStorage, fall back to localStorage if server state is empty

## 3. Answer Report Enrichment

- [x] 3.1 Update `cue_api/routes/audit.py` answer report download to merge review state into each suggestion entry (add `review_state` and `final_value` fields)
- [x] 3.2 Update `cue_ui/templates/answer_report.html` to display review decisions alongside suggestions (accepted/edited/dismissed badge per question)
- [x] 3.3 Write unit test: verify enriched report contains review state fields when state exists, omits them when state is absent

## 4. Testing

- [ ] 4.1 Smoke-test in browser: accept/dismiss/edit suggestions, reload page, verify state restored from server
- [ ] 4.2 Smoke-test cross-device: review in one browser, open same session URL in another, verify state appears
- [x] 4.3 Verify answer report download includes review state after reviewing suggestions
- [x] 4.4 Verify session deletion cleans up review_state.json
