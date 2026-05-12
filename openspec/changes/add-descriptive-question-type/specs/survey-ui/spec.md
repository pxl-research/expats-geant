## MODIFIED Requirements

### Requirement: Survey Rendering

The UI SHALL render a survey as an interactive form, deriving question layout and input controls
from the internal `Survey` model returned by the API. Question types SHALL map to appropriate
HTML input controls.

#### Scenario: Render choice question

- **WHEN** a question of type `single_choice` or `multiple_choice` is rendered
- **THEN** the UI displays labelled radio buttons or checkboxes respectively
- **AND** each answer option is shown with its text label

#### Scenario: Render open-ended question

- **WHEN** a question of type `open_ended` is rendered
- **THEN** the UI displays a textarea for free-text input

#### Scenario: Render slider question

- **WHEN** a question of type `slider` is rendered
- **THEN** the UI displays a range input bounded by `min_value` and `max_value` with the given `step`

#### Scenario: Render ranking question

- **WHEN** a question of type `ranking` is rendered
- **THEN** the UI displays answer options in a reorderable list

#### Scenario: Render descriptive item

- **WHEN** a question of type `descriptive` is rendered
- **THEN** the UI displays the text as static informational content
- **AND** no input control is shown
- **AND** no suggestion zone is rendered for this item
