## MODIFIED Requirements

### Requirement: Question Suggestion

The system SHALL generate improved versions of survey questions for clarity and consistency.

#### Scenario: Suggest reworded question

- **WHEN** an administrator requests a suggestion for a question
- **THEN** the system returns alternative phrasings with reasoning

#### Scenario: Suggest with style guide context

- **WHEN** a suggestion includes style guide context
- **THEN** the system enforces institutional style conventions in suggestions

#### Scenario: Suggest descriptive block text

- **WHEN** an administrator requests a suggestion for a descriptive item
- **THEN** the system treats it as informational text (not a question) and suggests improved wording appropriate for introductions, instructions, or contextual information

### Requirement: Question Validation

The system SHALL check questions against style guidelines and basic grammar rules.

#### Scenario: Validate question clarity

- **WHEN** a question is validated
- **THEN** the system flags unclear, ambiguous, or biased phrasing

#### Scenario: Validate QTI compliance (optional)

- **WHEN** a questionnaire is validated with the QTI adapter selected
- **THEN** the system checks that all questions use QTI 3.0-compatible types
- **AND** compliance is reported as an adapter-level concern, not a core validation failure

#### Scenario: Skip question-specific rules for descriptive items

- **WHEN** a descriptive item is validated
- **THEN** question-specific rules (e.g. double-barrelled question detection, leading question check) are skipped
- **AND** general text quality rules (grammar, clarity) still apply
