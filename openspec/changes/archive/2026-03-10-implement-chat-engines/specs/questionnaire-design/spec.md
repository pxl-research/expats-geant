## ADDED Requirements

### Requirement: Session Style Profile and Language

The system SHALL maintain a style profile per M-Chat session that influences all LLM-generated suggestions, validation feedback, and generated question text. The style profile SHALL include: a `language` field (ISO 639-1, default `"en"`), a `free_text` field for admin-typed style preferences, and a `document_summary` field populated when the admin uploads an institutional style guide document. If no style preferences are provided, the system SHALL apply sensible defaults: English language, neutral formal tone, and rules from the platform's survey design guidelines. The style profile SHALL persist for the lifetime of the session and survive session resume. The admin SHALL be able to update the language or free-text preference at any point during the session.

#### Scenario: Default style profile applied

- **WHEN** a new chat session is created without any style input
- **THEN** the style profile defaults to English language and neutral formal tone
- **AND** `defaults_applied` is set to `true` in the stored profile

#### Scenario: Admin sets language

- **WHEN** the admin updates the session language to a non-default value (e.g. `"nl"`)
- **THEN** all subsequent suggestions, validation messages, and generated questions are produced in that language
- **AND** the language setting persists across session resume

#### Scenario: Admin types style preferences

- **WHEN** the admin provides free-text style preferences (e.g. "formal tone, 5-point scales only")
- **THEN** the LLM incorporates these preferences in all subsequent suggestions and validation feedback

#### Scenario: Admin uploads institutional style guide

- **WHEN** an institutional style guide document is uploaded to the session
- **THEN** the document text is extracted and the LLM generates a concise summary of the style rules
- **AND** the summary is stored in the session style profile and used as context on all subsequent turns
