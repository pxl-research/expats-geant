# m-chat-ui Specification

## Purpose
TBD - created by archiving change implement-chat-ui. Update Purpose after archive.
## Requirements
### Requirement: Session Landing Page

The M-Chat UI SHALL provide a landing page that lists the authenticated user's active survey design sessions and allows starting a new session.

#### Scenario: Resume existing session

- **WHEN** an authenticated user visits the landing page
- **THEN** their active sessions are listed with titles and last-modified timestamps
- **AND** each session has a resume link that returns them to the chat interface

#### Scenario: Start new session

- **WHEN** a user clicks "Start new survey"
- **THEN** a new session is created and the user is redirected to the style setup page

### Requirement: Style Setup Page

The M-Chat UI SHALL present a style setup step after session creation where the user can set their language preference, type style notes, and optionally upload an institutional style guide document. The step SHALL be skippable to allow users to start chatting immediately with defaults applied.

#### Scenario: Set language and style

- **WHEN** a user selects a language and enters free-text style notes on the setup page
- **THEN** the style profile is saved and the user is redirected to the chat interface

#### Scenario: Upload style guide document

- **WHEN** a user uploads a style guide document on the setup page
- **THEN** an extracted style summary is shown inline for confirmation before proceeding

#### Scenario: Skip style setup

- **WHEN** a user clicks "Skip" on the setup page
- **THEN** English and neutral defaults are applied and the user proceeds directly to chat

### Requirement: Chat Interface

The M-Chat UI SHALL provide a conversational chat interface for iterative survey design. The interface SHALL display conversation history, a live preview of the current survey draft, and controls to upload source documents, reset the draft, or navigate to export.

#### Scenario: Send message and receive response

- **WHEN** a user sends a message in the chat interface
- **THEN** the assistant response is appended to the conversation
- **AND** if the draft survey was updated, the survey preview sidebar reflects the change

#### Scenario: Upload content document

- **WHEN** a user uploads a source document (slide deck, Word doc, PDF) in the chat
- **THEN** a topic summary is shown and the document is available as context for the LLM

#### Scenario: Reset draft

- **WHEN** a user clicks "Reset draft"
- **THEN** the draft survey and tag vocabulary are cleared
- **AND** the conversation history and style settings are preserved

### Requirement: Export and Publish Page

The M-Chat UI SHALL provide an export page where the user selects a target platform and either downloads the survey as a file or pushes it directly to the platform via its API.

#### Scenario: Push to platform

- **WHEN** a user selects LimeSurvey or Qualtrics and clicks "Publish"
- **THEN** the survey is pushed to the platform via its API
- **AND** the platform-assigned survey ID is displayed

#### Scenario: Download as file

- **WHEN** a user selects SurveyMonkey, QTI, or any file-based format and clicks "Export"
- **THEN** the survey file is downloaded in the selected format

