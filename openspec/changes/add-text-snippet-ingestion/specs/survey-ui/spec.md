## ADDED Requirements

### Requirement: Paste Text Snippet on Documents Page

The UI SHALL provide a textarea on the document upload page so users can type or paste
plain text as context for answer suggestions, as an alternative or supplement to file uploads.

An optional label field SHALL allow users to name the snippet (e.g. "My CV", "Project notes").
When omitted the backend applies a default label.

#### Scenario: Submit text snippet

- **WHEN** the user types or pastes text into the textarea and submits the form
- **THEN** the text is sent to `POST /upload-text` and ingested into the session

#### Scenario: Text field is optional

- **WHEN** the user submits the form with an empty textarea
- **THEN** the text field is ignored and only file uploads (if any) are processed

#### Scenario: File upload and text snippet combined

- **WHEN** the user both selects files and fills in the textarea before submitting
- **THEN** both the files and the text snippet are ingested into the session
