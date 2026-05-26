# Proposal: Granular survey mutation tools and endpoints

## Why

A pilot user reported that Shape returned `survey_updated: false` after a
five-minute wait, with the updated survey JSON pasted literally into the chat
reply (PR conversation, "Bij het prompten van een grote bevraging…"). The
survey was ~150 questions. The proximate cause is the model truncating the
`<survey_update>` JSON block when output tokens run out: the regex never
matches a closing tag, so the raw text leaks through and the draft is never
saved. We already shipped a truncation guard (commit `f063656`) that turns
that failure mode into a clean user-facing message instead of garbage, but
the structural problem remains: **the chat turn forces the LLM to re-emit
the entire survey for every edit**, by mandate of the system prompt
("Output the COMPLETE survey every time").

For a 150-question survey this is ~30k–60k output tokens of JSON. Most
provider output ceilings sit between 8k and 16k tokens. So the chat-edit
path is structurally broken for any survey that grew past ~50 questions —
and every edit, no matter how small, pays the full re-emit cost in latency
and money.

The clean fix is to let the model express **changes as patches** rather
than as full-survey replays. The work has three parts:

1. A shared **mutation layer** (`shape_api/mutations.py`) of pure functions
   that apply add/update/delete operations to a `Survey` and raise typed
   errors. The single source of truth for "how do we mutate a draft".
2. A **granular tool surface** (eight tools) the LLM uses during a chat
   turn, each dispatching into the mutation layer.
3. A matching **HTTP endpoint surface** for direct caller-driven edits
   (visual editors, integrations, CLIs) backed by the same mutation layer.

Output size for a one-question edit collapses from ~30k tokens to ~50.

## What Changes

- **New `shape_api/mutations.py`** module: pure functions
  `apply_init_survey`, `apply_add_section`, `apply_update_section`,
  `apply_delete_section`, `apply_add_question`, `apply_update_question`,
  `apply_delete_question`. Each takes a `Survey`, returns a new `Survey`,
  raises typed errors (`NoSurveyDraft`, `SectionNotFound`,
  `QuestionNotFound`, `DuplicateId`, `InvalidPatch`).
- **Extended `shape_api/tools.py`**: seven new tool schemas alongside the
  existing `get_full_survey`, plus a dispatcher arm per tool that calls into
  `mutations.py`, persists the result, and returns a structured JSON
  response containing `status`, any error code/message, and the current
  `validation_issues` from `validate_survey`.
- **Renamed conceptually**: the tool that takes a full survey is exposed
  as `init_survey` (not `replace_survey`); the description biases the model
  toward calling it only for cold-start or wholesale restructure.
- **New HTTP endpoints** under `/chat/{session_id}/survey/`:
  - `POST /sections` — add section
  - `PATCH /sections/{section_id}` — update section
  - `DELETE /sections/{section_id}` — delete section
  - `POST /sections/{section_id}/questions` — add question
  - `PATCH /questions/{question_id}` — update question
  - `DELETE /questions/{question_id}` — delete question
  Each returns `{status, validation_issues}`. Each shares the same mutation
  function as the corresponding tool.
- **System prompt rewrite** in `shape_api/conversation.py`:
  - Delete *"Output the COMPLETE survey every time, not just the changed parts"*.
  - Delete the inline JSON schema block (the tool schemas already carry it).
  - Replace with a short list of available tools and one-sentence selection
    guidance per tool.
- **Iteration cap raised** from 3 to **25** to accommodate multi-edit
  turns. The cap-hit warning + user-facing fallback message stay.
- **Removed**: `_SURVEY_TAG_RE` and `_parse_chat_response`. The LLM no longer
  emits `<survey_update>` blocks; mutations go through tools. The
  truncation guard added in `f063656` remains in place, as it still
  protects the `init_survey` payload path.
- **Validation issues from each mutation** are returned in the tool
  response so the model can self-correct on the next iteration without
  bespoke post-processing. Today's "I also noticed: …" suffix in
  `execute_chat_turn` is removed; the model decides when to surface
  methodological concerns.
- **Section-size warnings** added to `validate_survey`: warning at >30
  questions per section, stronger nudge at >50. No hard cap.
- **The `survey_updated` response flag** becomes "any mutation tool
  succeeded during this turn", which the Shape UI already polls on.

## Impact

- **Affected specs:**
  - `questionnaire-design`: MODIFIED `Conversational Session API` (chat
    turn flow now driven by mutation tools, no `<survey_update>` tags,
    iteration cap 25). ADDED `Survey Mutation Tools` (the eight-tool
    surface, error catalogue, validation feedback). ADDED
    `Survey Mutation HTTP Endpoints` (the matching REST surface). ADDED
    `Section Size Methodological Warnings` (the soft 30/50 thresholds).
- **Affected code:**
  - `shape_api/mutations.py` — new module (pure functions + typed errors).
  - `shape_api/tools.py` — seven new tool schemas + dispatcher arms.
  - `shape_api/conversation.py` — prompt rewrite, drop tag regex, drop
    `_parse_chat_response`, raise iteration cap to 25.
  - `shape_api/routes/chat.py` — six new HTTP endpoints sharing the
    mutation layer.
  - `shape_api/validation_engine.py` (or equivalent) — section-size
    warnings.
  - `shape_api/models.py` — request/response models for the new endpoints
    (`SectionPatch`, `QuestionPatch`, response wrappers).
- **Behaviour change for clients:**
  - **Chat API contract**: unchanged externally. Same request/response
    shape; same `survey_updated` flag semantics from the caller's
    perspective.
  - **New HTTP endpoints**: additive. Existing callers continue to work.
  - **Internal observability**: `<survey_update>` tag warnings disappear
    from logs; new structured logs per mutation tool invocation appear.
- **Latency:** one-question edits drop from "regenerate 30k tokens" to
  "emit a 50-token patch" — order-of-magnitude faster on large surveys.
  Multi-edit turns ("translate all five section titles") cost N round-trips
  but each is small and fast.
- **Token cost:** dominated today by re-emitting unchanged questions;
  expected to drop by ~10–100× per edit on surveys >50 questions.
- **No data-shape changes.** The `Survey`/`Section`/`Question` models are
  untouched.
- **No database changes.**
