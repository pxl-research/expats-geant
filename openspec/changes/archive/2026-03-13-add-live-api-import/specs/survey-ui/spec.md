## ADDED Requirements

### Requirement: Live API Import Form

The UI SHALL provide a distinct "Import from Platform API" section on the survey upload
page as an alternative to file upload, supporting LimeSurvey and Qualtrics platforms.

The section SHALL display a prominent security warning informing the user that their
platform credentials will be transmitted to the server and that file upload is the
recommended approach.

Credential fields SHALL be conditional: selecting "LimeSurvey" shows API URL, username,
password, and survey ID fields; selecting "Qualtrics" shows API token, datacenter ID, and
survey ID fields.

#### Scenario: Successful API import via UI

- **WHEN** the user selects a platform, fills in valid credentials and survey ID, and submits
- **THEN** the form posts to the server, the survey is imported, and the user is redirected
  to the document upload step (same flow as file import)

#### Scenario: API import error shown in UI

- **WHEN** the server returns an error (400, 502, etc.)
- **THEN** the upload page is re-rendered with a descriptive error message and the form
  fields retain their previous values (except password fields, which are cleared)

#### Scenario: Security warning visible before credential fields

- **WHEN** the user views the upload page
- **THEN** the security warning is visible before any credential input fields are shown,
  regardless of which platform is selected
