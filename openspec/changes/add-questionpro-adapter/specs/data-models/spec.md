## ADDED Requirements

### Requirement: Question Validation Hint

The system SHALL define a `ValidationHint` Pydantic model that captures cross-platform validation intent for free-text answers. The model SHALL expose two fields:

- `kind`: optional `Literal["email", "url", "phone", "number", "date", "date_time", "regex"]`. Identifies the semantic validator intent.
- `pattern`: optional `str`. Required when `kind == "regex"`. MAY be supplied alongside a named `kind` to carry a platform-specific override.

The `ValidationHint` SHALL be reachable via an optional `validation_hint: ValidationHint | None` field on the `Question` model. Adapters SHALL round-trip this field against their platform's native validator surface where possible; unrecognized platform patterns SHALL leave `validation_hint` null and preserve the original pattern in adapter-specific `metadata` keys. Adapters SHALL NOT infer a named `kind` from an unfamiliar regex.

Date display format strings (e.g. `YYYY-MM-DD`, `DD/MM/YYYY`) SHALL NOT be stored on `ValidationHint.pattern`. They are presentation templates, not match expressions, and SHALL be carried in `question.metadata["display_format"]` instead. Internal exchange of date values SHALL canonicalize to ISO 8601.

#### Scenario: ValidationHint with named kind

- **WHEN** a `ValidationHint` is constructed with `kind="email"`
- **THEN** the instance is valid
- **AND** `pattern` is `None` unless explicitly supplied

#### Scenario: ValidationHint with regex kind

- **WHEN** a `ValidationHint` is constructed with `kind="regex"` and a non-empty `pattern`
- **THEN** the instance is valid

#### Scenario: ValidationHint with regex kind missing pattern

- **WHEN** a `ValidationHint` is constructed with `kind="regex"` and `pattern=None`
- **THEN** a `ValidationError` is raised identifying `pattern` as required when `kind == "regex"`

#### Scenario: ValidationHint with date kind

- **WHEN** a `ValidationHint` is constructed with `kind="date"` or `kind="date_time"`
- **THEN** the instance is valid
- **AND** any presentation format (e.g. `"YYYY-MM-DD"`) supplied by the caller is NOT stored on `pattern`

#### Scenario: ValidationHint with no kind and no pattern

- **WHEN** a `ValidationHint` is constructed with both `kind` and `pattern` set to `None`
- **THEN** the instance is valid but carries no validation intent

#### Scenario: Adapter preserves unrecognized regex without guessing a kind

- **WHEN** an adapter encounters a platform-native regex pattern that does not match a known named `kind`
- **THEN** the resulting `Question.validation_hint` is `ValidationHint(kind="regex", pattern=<original>)`
- **AND** the adapter does NOT set `kind` to `"email"`, `"date"`, or any other named value based on regex shape

## MODIFIED Requirements

### Requirement: Question Model

The system SHALL define a `Question` model supporting six core question types that represent the common denominator across QTI 3.0, Qualtrics, LimeSurvey, SurveyMonkey, and QuestionPro. The `metadata` dict SHALL serve as the escape hatch for platform-specific question properties. An optional `validation_hint: ValidationHint | None` field SHALL carry cross-platform validation intent for free-text answers and SHALL be meaningful only when `type == "open_ended"`.

#### Scenario: Multiple choice question

- **WHEN** a question is of type `multiple_choice`
- **THEN** it contains `answer_options` with text and identifiers

#### Scenario: Single choice question

- **WHEN** a question is of type `single_choice`
- **THEN** it contains exactly one selectable answer option (covers Likert scales, yes/no, dropdowns)

#### Scenario: Open-ended question

- **WHEN** a question is of type `open_ended`
- **THEN** it accepts free-text responses without predefined options
- **AND** it MAY carry an optional `validation_hint` capturing format intent (email, URL, phone, number, date, date_time, or a regex pattern)

#### Scenario: Ranking question

- **WHEN** a question is of type `ranking`
- **THEN** it contains orderable `answer_options`

#### Scenario: Slider question

- **WHEN** a question is of type `slider`
- **THEN** it contains `min_value`, `max_value`, and `step`

#### Scenario: Descriptive item

- **WHEN** a question is of type `descriptive`
- **THEN** it contains display text only, with no answer_options, no min/max, and `required` defaults to `False`
- **AND** it is rendered as static informational content in the UI
- **AND** no response is expected or collected for this item

#### Scenario: ValidationHint restricted to open_ended questions

- **WHEN** a `validation_hint` is set on a question whose `type` is anything other than `open_ended`
- **THEN** a `ValidationError` is raised identifying the question type and the `validation_hint` field
