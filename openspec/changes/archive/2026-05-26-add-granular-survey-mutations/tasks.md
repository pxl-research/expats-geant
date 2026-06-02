# Tasks

## 1. Mutation layer (pure functions, the foundation)

- [x] 1.1 Create `shape_api/mutations.py` with typed error classes:
  `NoSurveyDraft`, `SectionNotFound`, `QuestionNotFound`, `DuplicateId`,
  `InvalidPatch`. Each is a subclass of a common `MutationError` so
  callers can catch broadly.
- [x] 1.2 Implement `apply_init_survey(survey: Survey) -> Survey`. Idempotent
  pass-through (validation handled upstream by Pydantic).
- [x] 1.3 Implement `apply_add_section(survey, section, after_id=None) -> Survey`.
  Raises `NoSurveyDraft` if `survey is None`; raises `DuplicateId` if
  `section.id` already exists; inserts after `after_id` (or appends if
  `after_id is None`).
- [x] 1.4 Implement `apply_update_section(survey, section_id, fields) -> Survey`.
  `fields` is a `SectionPatch` Pydantic model (partial). Rejects any
  `questions` field with `InvalidPatch`. Raises `SectionNotFound`.
- [x] 1.5 Implement `apply_delete_section(survey, section_id) -> Survey`.
  Raises `SectionNotFound`. Removes section and all its questions.
- [x] 1.6 Implement `apply_add_question(survey, section_id, question, after_id=None) -> Survey`.
  Raises `SectionNotFound`, `DuplicateId`. Preserves the question's id
  when supplied. Inserts after `after_id` within the section.
- [x] 1.7 Implement `apply_update_question(survey, question_id, fields) -> Survey`.
  `fields` is a `QuestionPatch` Pydantic model (partial). Walks all
  sections to find the question. Raises `QuestionNotFound`.
- [x] 1.8 Implement `apply_delete_question(survey, question_id) -> Survey`.
  Walks all sections to find and remove. Raises `QuestionNotFound`.
- [x] 1.9 Define `SectionPatch` and `QuestionPatch` Pydantic models in
  `shape_api/models.py` mirroring `Section` / `Question` field-by-field
  but with every field `Optional` and default `None`. Configure
  `model_dump(exclude_unset=True)` semantics so callers can distinguish
  "field omitted" from "field set to null".
- [x] 1.10 Unit tests in `tests/test_shape_mutations.py`: one happy-path
  and one error-path test per mutation function. ~14 tests.
- [x] 1.11 Unit test: `add_question` preserves the supplied id (move
  case).
- [x] 1.12 Unit test: `delete_section` removes the section's questions
  along with it.
- [x] 1.13 Unit test: `update_section` rejects a body containing
  `questions` with `InvalidPatch`.

## 2. Section-size warnings in validation

- [x] 2.1 Locate the function that produces validation issues for a
  `Survey` (currently `validate_survey` in
  `shape_api/validation_engine.py`). Add a warning issue with code
  `section_dense` when any section has > 30 questions.
- [x] 2.2 Add a stronger-worded warning with code `section_overlong`
  when any section has > 50 questions (mutually exclusive with
  `section_dense`).
- [x] 2.3 Unit tests: 30-question section → no new warning;
  31-question → `section_dense`; 51-question → `section_overlong`,
  no `section_dense`.

## 3. LLM tool surface

- [x] 3.1 In `shape_api/tools.py`, define OpenAI-style tool schemas for
  the seven new tools (`init_survey`, `add_section`, `update_section`,
  `delete_section`, `add_question`, `update_question`,
  `delete_question`). Each parameter described and typed; descriptions
  are concise but include error-recovery hints (e.g.
  *"Call `get_full_survey` to list current section ids."*).
- [x] 3.2 Extend `dispatch_tool_call(name, arguments, base_path, session_id)`
  to handle each new tool name. For each: load the current draft, call
  the corresponding `apply_*` function, persist via `save_draft_survey`
  on success, run `validate_survey`, return the JSON envelope
  `{"status": "ok", "validation_issues": [...]}`.
- [x] 3.3 Map each `MutationError` subclass to a structured error
  envelope `{"status": "error", "code": "...", "message": "..."}`. The
  dispatcher never raises; it always returns a JSON string.
- [x] 3.4 Update the export list / module docstring of `shape_api/tools.py`
  to reflect the expanded surface.
- [x] 3.5 Unit tests in `tests/test_shape_tools.py`: one happy-path
  envelope check per tool, one error envelope check (e.g. delete a
  non-existent section → `section_not_found` envelope). ~14 tests.
- [x] 3.6 Unit test: a tool call that succeeds AND introduces a
  validation warning returns `status: ok` with the warning in
  `validation_issues`.

## 4. HTTP endpoint surface

- [x] 4.1 In `shape_api/models.py`, add request body models:
  `AddSectionRequest{section, after_id?}`,
  `AddQuestionRequest{question, after_id?}`. Reuse `SectionPatch` and
  `QuestionPatch` from task 1.9 as PATCH bodies. Add a single response
  model `MutationResponse{status, validation_issues}` used by every
  mutation endpoint.
- [x] 4.2 In `shape_api/routes/chat.py`, add six new endpoints
  (POST/PATCH/DELETE × sections/questions) per the table in
  `design.md`. Each: verify ownership via existing helper, load draft,
  call the appropriate `apply_*` function inside a try/except that
  maps `MutationError`s to `HTTPException` (`SectionNotFound`/
  `QuestionNotFound` → 404, `DuplicateId` → 409, `InvalidPatch` /
  `NoSurveyDraft` → 400). Persist the result, validate, return
  `MutationResponse`.
- [x] 4.3 Wire the rate limiter (`@limiter.limit("…/minute")`) on the
  mutation endpoints matching the existing PUT endpoint's policy.
- [x] 4.4 Integration tests in `tests/test_chat_conversational_api.py`
  under a new `TestSurveyMutationEndpoints` class. For each verb:
  happy path (status 200, draft mutated, validation issues returned),
  not-found (404), wrong-session (403), unauthenticated (401). One
  test covering an end-to-end edit sequence (POST section → POST
  question → PATCH question → GET survey verifies state).

## 5. Chat-turn rewrite

- [x] 5.1 In `shape_api/conversation.py`, remove `_SURVEY_TAG_RE` and
  `_parse_chat_response`.
- [x] 5.2 Remove the "Output the COMPLETE survey every time" instruction
  and the full inline JSON schema block from `build_system_prompt`.
- [x] 5.3 Add a concise tool overview to the system prompt: one
  sentence per tool, plus the rule "use `init_survey` only when no
  draft exists yet, or the user explicitly asks to restart". Mention
  the move pattern (delete + add preserving id) explicitly.
- [x] 5.4 Remove the "I also noticed: …" post-processing block from
  `execute_chat_turn`. The methodological-advisor behaviour moves into
  the LLM's reasoning via validation feedback in the tool responses.
- [x] 5.5 Change `MAX_TOOL_CALL_ITERATIONS` from 3 to 25. Update the
  comment above the constant.
- [x] 5.6 Update `execute_chat_turn` so `survey_updated` becomes
  "any mutation tool returned `status: ok` during this turn".
  Track this via a flag inside the tool-call loop; the existing
  per-call dispatch already returns a JSON string we can inspect.
- [x] 5.7 Pass the full tool set (`[GET_FULL_SURVEY_TOOL, INIT_SURVEY_TOOL, …]`)
  to `create_completion_full` instead of just `[GET_FULL_SURVEY_TOOL]`.
- [x] 5.8 The truncation guard from commit `f063656` stays. The
  cap-hit warning + fallback message stay. No other changes to the
  turn handler's outer control flow.
- [x] 5.9 Audit `shape_api/conversation.py` for any remaining
  references to `<survey_update>` (logs, warnings, comments) and
  remove them.

## 6. Tests — chat-turn end-to-end

- [x] 6.1 In `tests/test_chat_conversational_api.py`, retire or rewrite
  `test_chat_turn_survey_update_parsed` and `test_get_survey_after_update`
  (which mock a `<survey_update>` block) to instead mock a tool-call
  response that invokes the appropriate mutation tool.
- [x] 6.2 Add a test for a multi-tool turn: model issues
  `add_section` + `add_question` + `add_question` in parallel; the
  draft contains the new section with both questions after the turn;
  `survey_updated: true`.
- [x] 6.3 Add a test for the error-recovery loop: first tool response
  is `section_not_found`; second LLM iteration corrects the id and
  succeeds; `survey_updated: true`.
- [x] 6.4 Add a test for the move case: model issues `delete_question`
  + `add_question` with the same id and a new `section_id`; the
  question's id is preserved.
- [x] 6.5 Add a test that a pure Q&A turn (no tool calls) returns
  `survey_updated: false` and does not modify the draft.
- [x] 6.6 Keep the existing truncation-guard test
  `test_chat_turn_truncated_output_returns_clean_message` as-is — it
  still covers `init_survey` payload truncation.

## 7. Docs

- [x] 7.1 If a docs file like `docs/SHAPE_API.md` exists, document the
  new endpoints with request/response shapes. Otherwise, skip — the
  Pydantic models are the contract.
- [x] 7.2 Document the tool surface in `shape_api/tools.py`'s module
  docstring (names + one-line purpose each), so the prompt and the
  code agree.

## 8. Validation gates

- [x] 8.1 Run `ruff check shape_api/ m_shared/ tests/` — clean.
- [x] 8.2 Run `ruff format --check shape_api/ m_shared/ tests/` — clean.
- [x] 8.3 Run `.venv/bin/python -m pytest tests/ --no-cov -q` — green.
- [x] 8.4 Run `openspec validate add-granular-survey-mutations --strict`
  — clean.
- [x] 8.5 Manual smoke (after `docker compose up shape-api shape-ui`):
  open Shape UI, ask "add an email question to the persoonlijke
  gegevens section" on a 150-question pilot survey, verify the chat
  reply is short (one sentence), the survey preview refreshes with
  the new question, no `<survey_update>` text appears in chat, and
  the audit log shows one or two structured tool-call entries.
