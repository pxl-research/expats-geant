## ADDED Requirements

### Requirement: UI Internationalisation

The Shape UI SHALL display all user-facing text (labels, buttons, headings, placeholders,
error messages, status indicators) in the language specified by the session's style
profile. The system SHALL support the same 7 languages available for survey content:
English (en), Dutch (nl), French (fr), German (de), Spanish (es), Italian (it), and
Portuguese (pt).

Translation strings SHALL be stored in per-language JSON files under `shape_ui/i18n/`
and loaded via a shared helper module (`m_shared/i18n.py`). If a translation key is
missing for the active language, the system SHALL fall back to English.

For pages where no session context is available (login, unauthenticated error pages),
the UI SHALL default to English.

#### Scenario: UI displayed in session language

- **WHEN** a user with a Dutch (nl) style profile opens the chat interface
- **THEN** all UI labels, buttons, headings, and placeholders are displayed in Dutch
- **AND** the LLM response content remains in the language set by the LLM prompt (also Dutch)

#### Scenario: Fallback to English for missing translation

- **WHEN** a translation key is not present in the active language's JSON file
- **THEN** the English translation is displayed instead
- **AND** a warning is logged to aid development

#### Scenario: Unauthenticated pages default to English

- **WHEN** a user visits the login page or an error page without an active session
- **THEN** the UI is displayed in English

#### Scenario: Language change applies on next page load

- **WHEN** a user changes the survey language in the style settings
- **THEN** the UI language updates on the next page load or navigation

### Requirement: JavaScript Translation Support

The Shape UI SHALL provide translations to client-side JavaScript by injecting a
translation object into the page. JavaScript code SHALL reference translation keys
from this object for confirmation dialogs, dynamic status text, and button label
updates.

#### Scenario: JS confirmation dialog in session language

- **WHEN** a user with a French (fr) session clicks "Reset draft"
- **THEN** the browser confirmation dialog text is displayed in French

#### Scenario: JS status text in session language

- **WHEN** the chat interface shows a loading indicator for a German (de) session
- **THEN** the loading text is displayed in German

### Requirement: Translation Key Consistency Check

The system SHALL include a test that verifies all language JSON files contain the same
set of keys as the English source file (`en.json`). This ensures translations stay in
sync as new strings are added.

#### Scenario: All language files have matching keys

- **WHEN** the translation consistency test is run
- **THEN** it passes if every language file contains exactly the same keys as `en.json`

#### Scenario: Missing key detected

- **WHEN** a language file is missing a key that exists in `en.json`
- **THEN** the test fails and reports the missing key and language

## MODIFIED Requirements

### Requirement: Chat Interface

The Shape UI SHALL provide a conversational chat interface for iterative survey design.
The interface SHALL display conversation history, a live preview of the current survey
draft, and controls to upload source documents, reset the draft, or navigate to export.

When the chat endpoint returns structured validation issues alongside the assistant
reply, the UI SHALL render them as distinct, translatable notes below the reply text,
rather than displaying raw English validation strings.

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

#### Scenario: Validation issues rendered in session language

- **WHEN** a chat response includes structured validation issues
- **AND** the session language is Dutch (nl)
- **THEN** the validation notes are displayed in Dutch below the assistant reply
- **AND** each note is visually distinct from the LLM-generated text
