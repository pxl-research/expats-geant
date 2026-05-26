# Tasks

## 1. Model changes (data-models)

- [x] 1.1 Remove the `order` field from `Question` (`m_shared/models/question.py`)
  and the `"order": 0` entry in its `json_schema_extra` example.
- [x] 1.2 Remove the `order` field from `Section` (`m_shared/models/section.py`)
  and the `"order"` entry in its example.
- [x] 1.3 Confirm both models keep Pydantic's default `extra="ignore"` (no
  `extra="forbid"`), and add a unit test that loads a survey JSON containing a
  stray `order` key without error.

## 2. Adapter audit & fixes

- [x] 2.1 Switch the three exporters that emit an explicit platform order field
  to compute it from list index instead of the model field:
  SurveyMonkey section `position`, LimeSurvey `group_order`,
  LimeSurvey `question_order`.
  (QTI and Qualtrics need no change — they encode order by element/array
  position only: XML document order, Qualtrics flow + BlockElements lists.)
- [x] 2.2 Remove `order=` construction kwargs from import builders (all four
  adapters); dead `position`/`order` plumbing removed alongside.
- [x] 2.3 LimeSurvey import: list order preserved by the existing `["order"]`
  sorts; test asserts imported question id order (`test_question_order_imported`).
- [x] 2.4 Qualtrics import: flow/block-element order maps to list position
  (`test_question_order_follows_block_elements`).
- [x] 2.5 Grep confirms no exporter reads a `.order` attribute after 2.1.
- [x] 2.6 Round-trip tests preserve order through list position
  (LimeSurvey id round-trip; SurveyMonkey/QTI position/section-order tests).

## 3. Mutation layer (`shape_api/mutations.py`)

- [x] 3.1 `apply_move_question(survey, question_id, after_id=None, section_id=None)`.
- [x] 3.2 `apply_move_section(survey, section_id, after_id=None)`.
- [x] 3.3 Unit tests: within-section reorder, move to front, cross-section move
  (id preserved), unknown-id errors (`TestMoveQuestion` / `TestMoveSection`).

## 4. Patch / request models (`shape_api/models.py`)

- [x] 4.1 Remove `order` from `QuestionPatch` and `SectionPatch`.
- [x] 4.2 Add `MoveQuestionRequest{after_id?, section_id?}` and
  `MoveSectionRequest{after_id?}`.

## 5. Tool surface (`shape_api/tools.py`)

- [x] 5.1 Add `move_question` and `move_section` tool schemas and dispatcher arms.
- [x] 5.2 Remove `order` from the param descriptions.
- [x] 5.3 Update the module docstring to list the two new tools.
- [x] 5.4 Dispatcher tests: happy + error envelope for each move tool; patch
  rejects an `order` field.

## 6. HTTP endpoints (`shape_api/routes/chat.py`)

- [x] 6.1 `PATCH /chat/{session_id}/survey/questions/{question_id}/position`.
- [x] 6.2 `PATCH /chat/{session_id}/survey/sections/{section_id}/position`.
- [x] 6.3 Reuse `_run_mutation`; not-found → 404; rate-limit `10/minute`.
- [x] 6.4 Integration tests: happy / 404 / 403 / 401, plus an end-to-end reorder
  that a `GET /survey` confirms.

## 7. Chat prompt (`shape_api/conversation.py`)

- [x] 7.1 Replace the delete+add "move" instruction with `move_question` /
  `move_section` guidance.
- [x] 7.2 Chat-turn test drives `move_question` end-to-end with a mocked LLM
  (`test_chat_turn_move_preserves_question_id`) and a cross-adapter test confirms
  QTI and SurveyMonkey exports agree on list order
  (`test_export_order_agrees_across_qti_and_surveymonkey`). Whether the *live*
  model picks `move_question` for a phrased request remains a manual/spot-check
  item (10.5).

## 8. UI verification

- [x] 8.1 Confirmed `shape_ui` / `cue_ui` previews render list order (no
  sort-by-order); no `.order` reads in either UI.

## 9. Docs

- [x] 9.1 `docs/SHAPE_API.md` documents the two position endpoints and states
  ordering is by list position; `DATA_MODEL.md` / `ADAPTERS.md` updated.

## 10. Validation gates

- [x] 10.1 `ruff check` + `ruff format --check` clean on all changed files
  (one pre-existing, unrelated `UP042` remains on the `QuestionType` enum).
- [ ] 10.2 `mypy`: introduced zero new errors (verified against baseline). The 5
  pre-existing `qti.py` call-arg errors in code this change touched are now fixed
  (defaults passed explicitly). 7 unrelated, pre-existing errors remain in
  `routes/chat.py` (dict-vs-typed-model on style/messages responses) — left for a
  separate type-cleanup change.
- [x] 10.3 Full `pytest` suite green (1256 passed).
- [x] 10.4 `openspec validate simplify-survey-ordering --strict` clean.
- [x] 10.5 Live-stack smoke: `tests/scripts/e2e_reorder_spot_check.py` ran
  against the running stack — 16/16 checks passed; docker logs confirmed the real
  model drove `move_question` / `move_section` (`status=ok`). Since ordering is
  list-position-only, the correct order changes prove the right tool was chosen.
