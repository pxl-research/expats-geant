## ADDED Requirements

### Requirement: Answer Report Page

The UI SHALL provide a dedicated answer report page rendering the session's suggestion
results in a human-readable format. Each suggestion SHALL be presented as a card showing:
question text, suggested answer, reasoning (when available), and cited sources with
document name, position, and excerpt.

A "Download as JSON" link SHALL allow the user to save the raw report file.

#### Scenario: Report page renders all suggestions

- **WHEN** the user navigates to the answer report page after suggestions have been generated
- **THEN** one card per question is displayed with answer, reasoning, and citation details

#### Scenario: Report page with no suggestions

- **WHEN** the user navigates to the answer report page before any suggestion has been generated
- **THEN** an informative message is shown explaining that no suggestions are available yet

---

### Requirement: Answer Report Links on Review and Submission Pages

The UI SHALL provide a link to the answer report page on the survey review page and on
the submission confirmation page, so users can access their evidence trail before
deleting their session.

#### Scenario: Link visible on review page

- **WHEN** the user is on the survey review page
- **THEN** a "View answer report" link is visible linking to the report page

#### Scenario: Link visible on submission confirmation

- **WHEN** the user reaches the submission confirmation page
- **THEN** a "View answer report" link is visible before the session cleanup prompt
