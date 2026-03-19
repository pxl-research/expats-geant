## ADDED Requirements

### Requirement: Methodological Advisor Behaviour

During conversational survey design, the system SHALL proactively surface methodological
concerns after each edit that introduces a new issue, and SHALL ask the designer whether
the choice is intentional. The system SHALL NOT lecture unprompted on minor edits or
re-raise concerns that were already present before the edit.

The advisory behaviour SHALL be powered by the tier-1 validation engine (deterministic,
no extra LLM call per turn). At most two newly introduced issues SHALL be surfaced per
turn to avoid reply flooding. Each issue SHALL be framed as a brief observation followed
by "— was this intentional?" rather than as an instruction or criticism.

This requirement extends `Question Validation` (on-demand) with a proactive, in-context
advisory layer. The `/validate` endpoint behaviour is unchanged.

#### Scenario: Advisory note after introducing a new issue

- **WHEN** a chat turn produces a survey update that introduces one or more new
  validation warnings
- **THEN** the assistant reply includes a brief advisory note for up to two of the new
  issues, each phrased as an observation with "— was this intentional?"

#### Scenario: No advisory note when no new issues

- **WHEN** a chat turn produces a survey update but introduces no new validation issues
- **THEN** no advisory note is appended to the reply

#### Scenario: Pre-existing issues are not re-raised

- **WHEN** a survey update does not change the set of validation issues
- **THEN** the assistant does not mention those issues in the reply

---

### Requirement: Extended Tier-1 Methodological Checks

The deterministic validation tier SHALL include the following additional checks, all at
`warning` or `info` severity:

- **`social_desirability`** (warning): question text uses phrasing that implies a
  virtuous or socially expected answer (e.g. "do you regularly", "do you always",
  "do you make sure to")
- **`missing_neutral_option`** (info): a `single_choice` question has an even number
  of options and none of them contain a neutral-signalling label ("neither", "neutral",
  "no opinion", "n/a", "not applicable") — the scale forces a directional response
- **`unbalanced_anchors`** (warning): all answer options (three or more) lean the same
  sentiment direction, suggesting the scale is not balanced around a midpoint
- **`survey_fatigue`** (warning): the total number of questions across all sections
  exceeds the configured threshold (default: 30)

These checks complement the existing `double_barreled`, `leading_language`,
`scale_too_short`, `scale_too_long`, and `likert_unlabelled` checks.

#### Scenario: Social desirability flagged

- **WHEN** a question text contains phrasing that implies an expected virtuous answer
- **THEN** a `social_desirability` warning is returned by `validate_question()`

#### Scenario: Missing neutral option flagged

- **WHEN** a `single_choice` question has an even number of options with no neutral label
- **THEN** a `missing_neutral_option` info issue is returned

#### Scenario: Unbalanced anchors flagged

- **WHEN** all answer options in a scale lean the same sentiment direction
- **THEN** an `unbalanced_anchors` warning is returned

#### Scenario: Survey fatigue flagged

- **WHEN** the total question count across all sections exceeds the threshold
- **THEN** a `survey_fatigue` warning is returned by `validate_survey()`

#### Scenario: Clean question produces no new issues

- **WHEN** a well-formed, balanced question is validated
- **THEN** none of the new checks fire
