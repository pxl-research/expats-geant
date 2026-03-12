# Change: Add Session Cleanup Prompt at Flow Completion

## Why

Users currently have no in-context prompt to delete their session data after completing
a workflow. The DELETE endpoints exist on both APIs, but are not surfaced in the UIs.
A non-blocking prompt at the natural end of each flow reinforces the privacy-first design
and satisfies the GDPR right-to-deletion principle without forcing the user's hand.

## What Changes

### Completion points

**m-autofill** — `submitted.html` (responses submitted to platform).
Display-only surveys have no submit action, so no completion point is defined for them
in this change; they can be addressed separately if needed.

**m-chat** — `export_result.html` partial, triggered after:
- a successful platform push (`action == push`)
- the user clicks the "Save as…" download link (`action == download`)

### UI behaviour

A modal dialog appears at the completion point with:
- a short explanation that session data (documents, suggestions, vectors) can now be deleted
- a primary "Delete session data" button → calls the existing DELETE endpoint → redirects
  to the home/start page
- a secondary "Keep session" button → dismisses the modal, user stays on the page

The modal is non-blocking: dismissing it has no side effect. The session continues to
exist until TTL expiry or an explicit delete.

### Backend

No backend changes required. Both UIs already have the necessary DELETE routes and
`api_client.delete_session()` methods.

## Impact

- Affected specs: `survey-ui`, `m-chat-ui`
- Affected code: `m_ui/templates/submitted.html`,
  `m_chat_ui/templates/partials/export_result.html`
- No breaking changes
