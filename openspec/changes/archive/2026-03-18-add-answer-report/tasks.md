## 1. Backend — persist suggestion results
- [x] 1.1 After a successful suggestion in `POST /suggest` (and `POST /suggest/batch`),
        append the full result — question, answer, reasoning, and citations (source,
        position, excerpt) — to `{session_path}/answer_report.json` as a JSON array;
        create the file on first write
- [x] 1.2 Keep the existing `audit_logger.log_suggestion()` call unchanged

## 2. Backend — download endpoint
- [x] 2.1 Add `GET /answer-report/download` endpoint: read `answer_report.json` from
        the session directory; return 404 if no suggestions have been made yet;
        return the file as `application/json` with a `Content-Disposition: attachment`
        header

## 3. UI — API client
- [x] 3.1 Add `fetch_answer_report(token)` to `m_ui/api_client.py` calling
        `GET /answer-report/download` (token-scoped; no session_id parameter needed)

## 4. UI — report page
- [x] 4.1 Add `GET /session/{session_id}/answer-report` route to `router.py`; validate
        session_id via `get_survey`, fetch the report via the API client and pass it
        to the template
- [x] 4.2 Add `answer_report.html` template: render one card per question showing
        question text, suggested answer, reasoning (if present), and citations
        (source name, position, excerpt); include a "Download as JSON" link

## 5. UI — links to report
- [x] 5.1 Add a "View answer report" link on `survey.html` (review page) pointing to
        the report page
- [x] 5.2 Add a "View answer report" link on `submitted.html` pointing to the report
        page (positioned before the session cleanup prompt from `add-session-cleanup-prompt`)

## 6. Tests
- [x] 6.1 Unit test: suggestion result is appended correctly to `answer_report.json`
        (verify structure: question, answer, reasoning, citations)
- [x] 6.2 Unit test: multiple suggestions accumulate correctly (array grows)
- [x] 6.3 API integration test for `GET /answer-report/download`: returns file when
        suggestions exist, 404 when none
- [x] 6.4 Verify report file is removed when `DELETE /session` is called (session
        cleanup includes the whole session directory)
