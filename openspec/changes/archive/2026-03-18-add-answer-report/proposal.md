# Change: Add Answer Report for M-Autofill Sessions

## Why

When a user uploads documents or connects to an external API to get answer suggestions,
the LLM returns an answer, a reasoning chain, and detailed citations (source document,
position percentage, and an excerpt). This information is currently ephemeral: it is
returned in the API response and then lost. If the user submits responses or ends the
session, there is no record of *why* those answers were suggested.

The audit log captures that a suggestion occurred, but not the reasoning or citation
detail needed to reconstruct the evidence trail.

A downloadable answer report — persisted per session as suggestions are generated —
gives users a transparent record of what was suggested, on what basis, and from which
sources, before they choose to delete their session.

Note: the existing `GET /audit-report` endpoint remains unchanged. The answer report
is a separate, user-facing transparency document rather than a compliance event log.

## What Changes

- At suggestion time, the full result (question, answer, reasoning, citations with
  position and excerpt) is appended to a `answer_report.json` file in the session
  directory; this is lightweight and requires no schema changes
- New `GET /answer-report/download` endpoint returns the persisted report as a formatted
  JSON or human-readable text file
- New UI page `GET /session/{session_id}/answer-report` renders the report as a readable
  summary: one card per question, showing question text, suggested answer, reasoning, and
  cited sources with excerpts
- A "Download report" link on the review page and on `submitted.html` links to this page
  before the user deletes their session

## Impact

- Affected specs: `answer-report` (new capability), `survey-ui`
- Affected code: `m_autofill/api.py` (persist at suggestion time, new endpoint),
  `m_ui/router.py`, `m_ui/api_client.py`, `m_ui/templates/` (new report page,
  link on review + submitted pages)
- No breaking changes; suggestion endpoint response is unchanged
- Report file is deleted with the session (same TTL, same `DELETE /session` path)
