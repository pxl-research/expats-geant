# Tasks

## 1. Model changes (data-models)

- [ ] 1.1 Remove the `order` field from `Question` (`m_shared/models/question.py`)
  and the `"order": 0` entry in its `json_schema_extra` example.
- [ ] 1.2 Remove the `order` field from `Section` (`m_shared/models/section.py`)
  and the `"order"` entry in its example.
- [ ] 1.3 Confirm both models keep Pydantic's default `extra="ignore"` (no
  `extra="forbid"`), and add a unit test that loads a survey JSON containing a
  stray `order` key without error.

## 2. Adapter audit & fixes

- [ ] 2.1 Switch the three exporters that emit an explicit platform order field
  to compute it from list index instead of the model field:
  SurveyMonkey section `position` (`surveymonkey.py:170`),
  LimeSurvey `group_order` (`limesurvey.py:340`),
  LimeSurvey `question_order` (`limesurvey.py:354`).
  (QTI and Qualtrics need no change — they encode order by element/array
  position only: XML document order, Qualtrics flow + BlockElements lists.)
- [ ] 2.2 Remove `order=` construction kwargs from import builders:
  `qti.py` (219, 257, 306), `surveymonkey.py` (220, 268, 348),
  `qualtrics.py` (166, 485), `limesurvey.py` (145, 291).
- [ ] 2.3 LimeSurvey import: verify display order is preserved purely by list
  position via the existing `["order"]` sorts (groups `:193`, questions `:227`);
  add/adjust a test asserting list order equals source order.
- [ ] 2.4 Qualtrics import: verify flow/block-element order maps to list position
  (`:122–158`); add/adjust a test.
- [ ] 2.5 Grep to confirm no exporter reads a `.order` attribute after 2.1
  (QTI / Qualtrics / LimeSurvey already number from list index).
- [ ] 2.6 Per-adapter round-trip test: import a file with non-trivial order →
  export → order preserved through list position (no stored field).

## 3. Mutation layer (`shape_api/mutations.py`)

- [ ] 3.1 `apply_move_question(survey, question_id, after_id=None, section_id=None)`:
  locate the question, remove it from its current section, resolve the target
  section (`section_id` or current), insert (after `after_id`; omit = front).
  Raise `QuestionNotFound` / `SectionNotFound`.
- [ ] 3.2 `apply_move_section(survey, section_id, after_id=None)`: remove and
  reinsert within `survey.sections`. Raise `SectionNotFound`.
- [ ] 3.3 Unit tests: within-section reorder, move to front, cross-section move
  (id preserved), unknown-id errors.

## 4. Patch / request models (`shape_api/models.py`)

- [ ] 4.1 Remove `order` from `QuestionPatch` and `SectionPatch`.
- [ ] 4.2 Add `MoveQuestionRequest{after_id?, section_id?}` and
  `MoveSectionRequest{after_id?}`.

## 5. Tool surface (`shape_api/tools.py`)

- [ ] 5.1 Add `move_question` and `move_section` tool schemas and dispatcher arms.
- [ ] 5.2 Remove `order` from the `_QUESTION_PARAM`, `_SECTION_PARAM`,
  `_QUESTION_PATCH_PARAM`, and `_SECTION_PATCH_PARAM` descriptions.
- [ ] 5.3 Update the module docstring to list the two new tools.
- [ ] 5.4 Dispatcher tests: happy + error envelope for each move tool.

## 6. HTTP endpoints (`shape_api/routes/chat.py`)

- [ ] 6.1 `PATCH /chat/{session_id}/survey/questions/{question_id}/position`
  (body `MoveQuestionRequest`).
- [ ] 6.2 `PATCH /chat/{session_id}/survey/sections/{section_id}/position`
  (body `MoveSectionRequest`).
- [ ] 6.3 Reuse `_run_mutation`; map not-found → 404; rate-limit `10/minute`.
- [ ] 6.4 Integration tests: happy / 404 / 403 / 401, plus an end-to-end reorder
  that a `GET /survey` confirms.

## 7. Chat prompt (`shape_api/conversation.py`)

- [ ] 7.1 Replace the delete+add "move" instruction with `move_question` /
  `move_section` guidance.
- [ ] 7.2 Test: a reorder request drives `move_question`, not `update_question`.

## 8. UI verification

- [ ] 8.1 Grep `shape_ui` and `cue_ui` templates/static for any sort-by-order;
  confirm previews render list order (shape_ui already does). Fix if any found.

## 9. Docs

- [ ] 9.1 `docs/SHAPE_API.md`: document the two position endpoints and state that
  ordering is by list position.

## 10. Validation gates

- [ ] 10.1 `ruff check` + `ruff format --check` clean.
- [ ] 10.2 `mypy` clean.
- [ ] 10.3 Full `pytest` suite green.
- [ ] 10.4 `openspec validate simplify-survey-ordering --strict` clean.
- [ ] 10.5 Manual smoke: reorder via chat → preview reflects the new order; QTI
  and SurveyMonkey exports agree.
