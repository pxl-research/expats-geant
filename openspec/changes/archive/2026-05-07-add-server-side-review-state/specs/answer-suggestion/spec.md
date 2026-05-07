## ADDED Requirements

### Requirement: Review State API

The system SHALL provide API endpoints for persisting and retrieving per-question review
state within a Cue session. Review state tracks the respondent's decision for each
suggestion: accepted, dismissed, edited, or pending.

`PUT /review-state/{question_id}` SHALL save the review state for a single question.
The request body SHALL include `state` (one of `accepted`, `dismissed`, `edited`) and
optionally `value` (the respondent's answer text), `selected_id` (matched choice ID for
single-choice questions), or `selected_ids` (matched choice IDs for multiple-choice
questions).

`GET /review-state` SHALL return the full review state map for the session as a JSON
object keyed by question ID.

Review state SHALL be stored as `review_state.json` in the session directory and
deleted automatically when the session is deleted.

#### Scenario: Save accepted state

- **WHEN** `PUT /review-state/q_1` is called with `{"state": "accepted", "value": "36 months"}`
- **THEN** the review state for question `q_1` is persisted
- **AND** subsequent `GET /review-state` includes `q_1` with state `accepted`

#### Scenario: Save dismissed state

- **WHEN** `PUT /review-state/q_2` is called with `{"state": "dismissed"}`
- **THEN** the review state for question `q_2` is persisted as dismissed

#### Scenario: Save edited state with choice selection

- **WHEN** `PUT /review-state/q_3` is called with `{"state": "edited", "selected_ids": ["opt_a", "opt_c"]}`
- **THEN** the review state for question `q_3` is persisted with the edited selections

#### Scenario: Load full review state

- **WHEN** `GET /review-state` is called for a session with saved review decisions
- **THEN** a JSON object is returned mapping each reviewed question ID to its state

#### Scenario: Load empty review state

- **WHEN** `GET /review-state` is called for a session with no saved review decisions
- **THEN** an empty JSON object is returned

#### Scenario: State overwritten on re-review

- **WHEN** a question's review state is saved multiple times (e.g. accepted then edited)
- **THEN** only the latest state is retained
