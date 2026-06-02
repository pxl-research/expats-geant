# Design: Granular survey mutation tools and endpoints

## Context

Shape's chat-edit path currently makes the LLM emit the entire updated
survey inside `<survey_update>` tags on every structural change. The
system prompt mandates *"Output the COMPLETE survey every time, not just
the changed parts"*. For surveys above ~50 questions this exceeds typical
provider output ceilings, the model truncates mid-JSON, the regex parser
fails, and the partial JSON leaks into the chat. Truncation guard
`f063656` cleans up the symptom but the structural cost remains: every
edit pays full re-emit price in tokens and latency.

The fix is to let the model express *changes as patches* rather than
*surveys as wholes*. This requires a shared mutation layer, a granular
tool surface for the LLM, and a matching HTTP endpoint surface for
caller-driven edits.

## Goals

- One-question edits cost ~50 output tokens, not ~30 000.
- A 150-question survey is editable through chat without ever
  hitting the output ceiling.
- LLM tool calls and HTTP endpoints share one mutation implementation —
  identical semantics, single test surface.
- Validation feedback flows back to the LLM after each mutation so the
  model self-corrects on the next iteration; no bespoke post-processing.
- The chat turn API contract is unchanged for existing callers
  (`survey_updated` flag, message text, status codes).

## Non-goals

- Multi-revision history or undo. The draft is still single-state.
- Concurrent-edit reconciliation (CRDT / OT). Last write wins.
- Bulk operations as first-class tools (`add_questions([...])`,
  `reorder_questions([...])`). We will revisit if telemetry shows the
  per-question round-trip count is genuinely painful.
- Removing the existing `PUT /chat/{sid}/survey` endpoint. It stays for
  full-survey replacements from UI form editors.
- Hard limits on section size. We add soft warnings only.

## Architecture

### Three-layer split

```
shape_api/
├── mutations.py       (pure functions, the single source of truth)
├── tools.py           (LLM tool surface → mutations.py)
└── routes/chat.py     (HTTP endpoints → mutations.py)
```

`mutations.py` is pure: each function takes a `Survey`, returns a new
`Survey`, raises typed errors. No I/O, no persistence, no LLM concerns.
Both the tool dispatcher and the HTTP route handlers load the draft,
call the mutation, validate, and save — the I/O wrapping is the only
duplicated logic, and it is two helpers.

### Tool surface

Eight tools advertised to the LLM:

| Tool | Signature (informal) | Notes |
|---|---|---|
| `get_full_survey` | `()` | Existing. Read authoritative state. |
| `init_survey` | `(survey: Survey)` | Create from scratch or wholesale restructure. Truncation-prone path; protected by `f063656`. |
| `add_section` | `(section: Section, after_id?: str)` | Insert. ID supplied by model. |
| `update_section` | `(section_id: str, fields: SectionPatch)` | Partial patch — title/description/order/metadata. NOT questions. |
| `delete_section` | `(section_id: str)` | Removes section and its questions. |
| `add_question` | `(section_id: str, question: Question, after_id?: str)` | Insert. ID preserved if supplied (move case). |
| `update_question` | `(question_id: str, fields: QuestionPatch)` | Partial patch. The workhorse. |
| `delete_question` | `(question_id: str)` | — |

### Tool response shape

Every mutation tool returns the same JSON envelope:

```json
{
  "status": "ok",
  "validation_issues": [{"severity": "warning", "code": "...", "message": "...", "question_id": "..."}]
}
```

Or on error:

```json
{
  "status": "error",
  "code": "section_not_found",
  "message": "Section 'sec_demo' not found. Call get_full_survey to list current sections."
}
```

The validation issues flow back into the LLM's next iteration. The model
decides whether to re-edit or to narrate the concern to the user. Today's
hard-coded *"I also noticed: …"* post-processing in
`execute_chat_turn` is removed; the methodological-advisor behaviour
moves into the model's reasoning where it belongs.

### Error catalogue

Five typed errors are sufficient:

| Error code | When | Recovery hint included in message |
|---|---|---|
| `no_survey_draft` | Any mutation called before `init_survey` | "Call init_survey first." |
| `section_not_found` | `section_id` unknown | "Call get_full_survey to list current sections." |
| `question_not_found` | `question_id` unknown | Same. |
| `duplicate_id` | `add_*` called with an id that already exists | "IDs must be unique within a survey." |
| `invalid_patch` | Patch body fails Pydantic validation | The specific field error. |

Errors are exposed as exception classes in `mutations.py` and converted
to the JSON envelope by both the tool dispatcher and the HTTP route
handlers (HTTP returns 404 for not-found, 409 for duplicate, 400 for
invalid).

### HTTP surface

Mirror the tool surface as REST endpoints, sharing `mutations.py`:

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/chat/{sid}/survey` | — | full Survey (existing) |
| `PUT` | `/chat/{sid}/survey` | `Survey` | `{status, validation_issues}` (existing) |
| `POST` | `/chat/{sid}/survey/sections` | `{section, after_id?}` | `{status, validation_issues}` |
| `PATCH` | `/chat/{sid}/survey/sections/{section_id}` | `SectionPatch` | `{status, validation_issues}` |
| `DELETE` | `/chat/{sid}/survey/sections/{section_id}` | — | `{status, validation_issues}` |
| `POST` | `/chat/{sid}/survey/sections/{section_id}/questions` | `{question, after_id?}` | `{status, validation_issues}` |
| `PATCH` | `/chat/{sid}/survey/questions/{question_id}` | `QuestionPatch` | `{status, validation_issues}` |
| `DELETE` | `/chat/{sid}/survey/questions/{question_id}` | — | `{status, validation_issues}` |

URL shape rationale: question routes are *flat* (not nested under
section) because question IDs are unique within a survey and the parent
section isn't needed for PATCH/DELETE — same shape GitHub uses for
issues vs. pull-request reviews. Section routes stay nested because that
is the only context where section IDs make sense.

All mutation endpoints reuse the existing JWT + session-ownership
middleware via the `request.state.session` mechanism; no new auth path.

### Chat-turn rewrite

The chat-turn loop (`execute_chat_turn` in `shape_api/conversation.py`)
becomes a thin orchestrator:

1. Build messages (system prompt + history + user message).
2. Call LLM with `[get_full_survey, init_survey, add_section, …]` tool
   set.
3. If response has tool calls: dispatch each into `mutations.py`,
   persist, and append the structured JSON response (including
   `validation_issues`) as a `role: "tool"` message. Continue.
4. If response is text only: that's the final assistant message. Exit.
5. Cap at **25** iterations. On cap-hit, log a warning and return the
   user-facing "couldn't complete within budget" message we already
   have.

`survey_updated = any_mutation_tool_returned_status_ok_during_this_turn`.

The `<survey_update>` regex and `_parse_chat_response` are deleted. The
truncation guard (`finish_reason == "length"` detection) stays — it now
protects the `init_survey` payload path, which is still capable of
emitting a survey-sized blob.

### Iteration cap = 25

Reasoning (telemetry-anchored estimates):

| Turn type | Expected iterations |
|---|---:|
| Plain Q&A (no tool) | 1 |
| Single edit | 2 (get + mutation) |
| Translate 5 section titles | 6 |
| Rewrite 20 questions in a section | 22 |
| Bootstrap a 50-question survey from a document | 1 (init_survey) |
| Pathological / model thrashing | ≥30 |

25 covers all everyday workflows with margin. Above 25 the model is
probably stuck in a loop; the cap-hit warning + user-facing fallback
already exists in the turn handler.

### System prompt changes

Removed:
- *"When you propose changes to the survey, output the complete updated
  survey JSON inside <survey_update> tags. Only include <survey_update>
  when proposing structural changes — for questions or explanations,
  respond with plain text."*
- *"Output the COMPLETE survey every time, not just the changed parts"*.
- The full inline JSON schema block.

Replaced with: one paragraph listing the eight tools with
one-sentence purpose each, plus the rule "use `init_survey` only when no
draft exists or the user explicitly asks to start over". The compact
survey summary (sections + IDs + question text + IDs) stays unchanged so
the model can pick the right `section_id` / `question_id` for surgical
edits.

### Section-size warnings

In `shape_api/validation_engine.py` (or wherever `validate_survey` lives
— exact path is an implementation detail), add two thresholds:

- **`section_dense`** (severity: warning) when a section has >30
  questions. Message: *"Section '{title}' has {n} questions — consider
  splitting into thematic subsections to reduce respondent fatigue."*
- **`section_overlong`** (severity: warning) when >50. Message:
  *"Section '{title}' has {n} questions — strong recommendation to
  split."*

No hard cap; psychometric instruments (NEO-PI, MMPI batteries)
legitimately exceed 50 items. The warnings reach the LLM via the
mutation tool response and reach HTTP callers via the same response
envelope.

## Trade-offs

### Eight tools vs. four

We considered collapsing add/update into `replace_section` / `upsert`
shapes. We rejected for these reasons:

- **Symmetry across section and question.** Add/update/delete is the
  same mental model for both, which models pick reliably.
- **Update partials are a major token win.** A
  `update_question(qid, {"text": "..."})` call is ~50 tokens. A
  collapsed upsert that requires the full question payload is ~300
  tokens. Across a typical edit session this compounds.
- **Clearer errors.** Add can fail with `duplicate_id`; update can fail
  with `question_not_found`. An upsert would have to silently choose
  between the two paths.

### No dedicated `move_question` tool

Moving = delete from old section + add to new section, expressible as
parallel tool calls in a single iteration. Models reliably preserve the
question id across the pair when the system prompt mentions: *"To move
a question, call `delete_question` then `add_question` and pass the
original question id through unchanged."*

If telemetry shows the model fumbles moves (generates a new id, breaks
links), we add `move_question(question_id, section_id, order?)` as a
thin convenience tool later. Don't pre-build it.

### Keeping `PUT /chat/{sid}/survey`

This endpoint already exists for form-editor flows. We keep it. It
overlaps semantically with `init_survey`, but they serve different
clients (HTTP vs. LLM tool) and removing it would break the existing
UI. Two front doors into the same mutation primitive is fine.

### Validation issues in tool response vs. post-processing

Today's chat turn runs `validate_survey` after a `<survey_update>` and
appends "I also noticed: …" suffixes to the assistant text. With
granular tools, validation runs after every mutation and the issues
become part of the tool response the LLM sees on its next iteration.
The model decides when (and whether) to surface a concern to the user.

This is strictly more flexible. The model can:
- Re-edit silently to fix a `leading_question` warning before the user
  ever sees it.
- Apply the change, then in the next conversational reply raise the
  concern ("I added the question, but its wording is a bit leading —
  was that intentional?").
- Apply the change without comment when the warning isn't material.

We lose the certainty that *every* warning is surfaced verbatim, but
the current behaviour already truncates to two issues
(`introduced[:2]`) and isn't comprehensive either. The trade is worth
it.

## Open questions deferred to implementation

- Exact pydantic shape of `SectionPatch` / `QuestionPatch`. Likely
  `model_dump(exclude_unset=True)` semantics so that any field omitted
  in the patch is left untouched.
- Whether to persist the draft after *every* tool call within a turn,
  or batch and save at the end. We will save after every call for
  crash safety; the cost is negligible (one JSON write per tool
  invocation).
- Whether `update_section` should accept a `questions` field at all
  (and reject it explicitly), or silently ignore it. We will reject
  with `invalid_patch` to keep the contract honest.
