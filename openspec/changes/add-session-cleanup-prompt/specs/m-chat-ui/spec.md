## ADDED Requirements

### Requirement: Session Cleanup Prompt on Export Completion

After a survey is successfully exported or published, the UI SHALL display a non-blocking
modal prompt offering the user the option to delete their session data.

The modal SHALL provide a primary "Delete session data" action and a secondary "Keep
session" dismiss, with the same behaviour as defined in `survey-ui`.

The prompt SHALL be shown:
- immediately after a successful platform push
- after the user clicks the "Save as…" download link for a file export (with a brief
  delay so the download is initiated first)

#### Scenario: Modal appears after successful platform push

- **WHEN** a survey is successfully published to a platform
- **THEN** the cleanup modal is shown in the export result area

#### Scenario: Modal appears after file download

- **WHEN** the user clicks the "Save as…" link to download the exported survey file
- **THEN** the download begins and the cleanup modal appears shortly after

#### Scenario: User deletes session data

- **WHEN** the user clicks "Delete session data" in the modal
- **THEN** the session is deleted and the user is redirected to the home page

#### Scenario: User keeps session

- **WHEN** the user dismisses the modal
- **THEN** the modal closes and the session remains intact
