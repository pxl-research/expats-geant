## ADDED Requirements

### Requirement: Platform Adapter Abstraction

The system SHALL provide a `SurveyAdapter` base class defining a common interface for all platform-specific import/export adapters. Each adapter SHALL implement `import_survey(raw: str) -> Survey` and `export_survey(survey: Survey) -> str`. Supported adapters for MVP: QTI 3.0, LimeSurvey, Qualtrics, SurveyMonkey.

#### Scenario: Import via adapter

- **WHEN** a questionnaire file is submitted with a specified platform format
- **THEN** the corresponding adapter is selected and converts the file to the internal `Survey` model
- **AND** unmappable platform-specific fields are preserved in the `metadata` dict

#### Scenario: Export via adapter

- **WHEN** a questionnaire is exported with a specified target format
- **THEN** the corresponding adapter serializes the internal `Survey` model to the platform format
- **AND** fields present only in `metadata` that are relevant to the target platform are included

#### Scenario: Cross-platform round-trip

- **WHEN** a questionnaire is imported from platform A and exported to platform B
- **THEN** all questions, answer options, and section structure are preserved
- **AND** platform-specific fields not supported by platform B are gracefully dropped

## MODIFIED Requirements

### Requirement: Question Validation

The system SHALL check questions against style guidelines and basic grammar rules.

#### Scenario: Validate question clarity

- **WHEN** a question is validated
- **THEN** the system flags unclear, ambiguous, or biased phrasing

#### Scenario: Validate QTI compliance (optional)

- **WHEN** a questionnaire is validated with the QTI adapter selected
- **THEN** the system checks that all questions use QTI 3.0-compatible types
- **AND** compliance is reported as an adapter-level concern, not a core validation failure

## REMOVED Requirements

### Requirement: QTI 3.0 Import
**Reason**: Superseded by the Platform Adapter Abstraction requirement; QTI import is now implemented as `adapters/qti.py`.
**Migration**: No API change — import endpoint gains an optional `format` parameter (default: `qti`).

### Requirement: QTI 3.0 Export
**Reason**: Superseded by the Platform Adapter Abstraction requirement; QTI export is now implemented as `adapters/qti.py`.
**Migration**: No API change — export endpoint gains an optional `format` parameter (default: `qti`).
