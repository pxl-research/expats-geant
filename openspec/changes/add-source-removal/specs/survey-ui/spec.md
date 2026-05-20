## ADDED Requirements

### Requirement: Per-Row Source Remove Control

The survey UI SHALL render a remove (✕) control on every row of the
sources list, on both the pre-review documents page and the mid-review
upload widget. Clicking the control SHALL prompt the user for
confirmation via a browser-native `confirm()` dialog naming the source.
On confirmation, the UI SHALL send `DELETE /session/{id}/documents/{name}`
(URL-encoding the name) and, on a 200 response, refresh the sources list
and document count via the existing `window.refreshSessionStats()` flow.

The control SHALL be present in both the server-side initial render and
the JavaScript-rendered re-render so the layout is consistent before
and after hydration.

#### Scenario: Remove control on every row

- **WHEN** the documents page or the mid-review widget renders a
  non-empty sources list
- **THEN** each row includes a ✕ remove control next to (or after) the
  source name

#### Scenario: Confirmation guard before removal

- **WHEN** the user clicks ✕ on a source row
- **THEN** a `confirm()` dialog appears naming the source
- **AND** if the user cancels, no request is sent and the list is unchanged

#### Scenario: Successful removal refreshes the list

- **WHEN** the user confirms the removal and the API returns HTTP 200
- **THEN** the UI calls `window.refreshSessionStats()` and the removed
  row disappears from the list
- **AND** the document count decrements accordingly

### Requirement: Source Removal Error Surfacing

The UI SHALL surface remove-request failures inline near the affected
row, while leaving the row in place so the user can retry. A 404
response (the source is already gone) SHALL be treated as success: the
UI refreshes the list and no error is shown. Other errors (network
failures, HTTP 4xx/5xx other than 404, unexpected server responses)
SHALL render an inline error block describing the failure.

#### Scenario: 404 treated as already-removed

- **WHEN** the DELETE request returns HTTP 404 (the source is no longer
  present, e.g. because another tab removed it first)
- **THEN** the UI refreshes the sources list without showing an error
- **AND** the row disappears on refresh

#### Scenario: Network or server error rendered inline

- **WHEN** the DELETE request fails with a non-404 error
- **THEN** the UI renders an inline error block near the row describing
  the failure
- **AND** the row remains in the list so the user can retry

### Requirement: Removal Does Not Affect Existing Review State

Removing a source SHALL NOT modify any cached suggestions, accepted
answers, dismissed answers, or edits in the user's review state. The
sources list reflects the current evidence set; the review state
continues to reflect the user's decisions about suggestions that were
generated previously.

#### Scenario: Cached suggestions unchanged after removal

- **WHEN** the user removes a source while in the mid-review widget
- **THEN** all previously rendered suggestions on the page remain
  exactly as they were
- **AND** no automatic regeneration is triggered

#### Scenario: Accepted answers preserved

- **WHEN** the user has accepted a suggestion citing source S
- **AND** the user removes source S
- **THEN** the accepted answer remains accepted with its original text
  and citation
