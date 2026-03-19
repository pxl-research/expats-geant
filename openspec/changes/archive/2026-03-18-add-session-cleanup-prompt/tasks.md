## 1. Shared modal component
- [x] 1.1 Add a reusable inline modal partial (`base.html` or a dedicated
        `partials/session_cleanup_modal.html`) with: explanation text, "Delete session
        data" button, "Keep session" dismiss button, and minimal CSS
- [x] 1.2 Add shared JS (inline or in a static file) for show/hide and the DELETE +
        redirect call; accept `session_id` and `delete_url` as parameters

## 2. m-autofill — submitted page
- [x] 2.1 Include the modal in `submitted.html` and trigger it automatically on page load
- [x] 2.2 Wire the "Delete session data" button to call `DELETE /session` (m-autofill
        endpoint) then redirect to `/`

## 3. m-chat — export result partial
- [x] 3.1 Include the modal in `export_result.html` and trigger it after a successful
        push (`action == push`)
- [x] 3.2 For `action == download`: trigger the modal when the user clicks the
        "Save as…" download link (fire after a short delay so the download starts first)
- [x] 3.3 Wire the "Delete session data" button to call
        `DELETE /session/{session_id}` (m-chat endpoint) then redirect to `/`

## 4. Tests
- [x] 4.1 Verify `submitted.html` renders the modal markup (template render test)
- [x] 4.2 Verify `export_result.html` renders the modal markup for push and download
        action variants
