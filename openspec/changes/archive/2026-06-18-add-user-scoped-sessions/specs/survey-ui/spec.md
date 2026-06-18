## ADDED Requirements

### Requirement: Session List Page

The Cue UI SHALL display a session list page after login, showing all active sessions
for the authenticated user. Each session entry SHALL display the session label (derived
from survey title or filename), creation date, and status. The page SHALL provide
options to resume an existing session or start a new one.

#### Scenario: User with existing sessions

- **WHEN** an authenticated user navigates to the session list page
- **THEN** all active sessions are displayed with label, date, and status
- **AND** each session has a "Resume" action that navigates to the review page

#### Scenario: User starts a new session

- **WHEN** a user clicks "New session" on the session list page
- **THEN** a new session is created via the API
- **AND** the user is redirected to the upload/import page for the new session

#### Scenario: User with no sessions

- **WHEN** an authenticated user has no active sessions
- **THEN** the session list page shows an empty state message
- **AND** the "New session" action is prominently displayed

### Requirement: Session Selection Flow

The Cue UI SHALL redirect users to the session list page after login instead of
directly to the upload page. Session-scoped pages (review, documents, answer report)
SHALL require a selected session. If no session is selected, the user SHALL be
redirected to the session list page.

#### Scenario: Post-login redirect

- **WHEN** a user completes OIDC login
- **THEN** they are redirected to the session list page

#### Scenario: Access session-scoped page without selection

- **WHEN** a user navigates to a session-scoped page without a valid session
- **THEN** they are redirected to the session list page
