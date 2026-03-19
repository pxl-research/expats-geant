## ADDED Requirements

### Requirement: Session Cleanup Prompt on Submission Completion

After responses are successfully submitted to the survey platform, the UI SHALL display
a non-blocking modal prompt offering the user the option to delete their session data.

The modal SHALL explain that documents, suggestions, and vectors can now be removed, and
provide a primary "Delete session data" action and a secondary "Keep session" dismiss.

Selecting "Delete session data" SHALL call the session deletion endpoint and redirect the
user to the start page. Dismissing the modal SHALL have no side effect.

#### Scenario: Modal appears after successful submission

- **WHEN** the user lands on the submission confirmation page
- **THEN** a modal prompt is shown offering to delete session data

#### Scenario: User deletes session data

- **WHEN** the user clicks "Delete session data" in the modal
- **THEN** the session is deleted and the user is redirected to the home page

#### Scenario: User keeps session

- **WHEN** the user clicks "Keep session" or dismisses the modal
- **THEN** the modal closes and the user remains on the confirmation page with the session intact
