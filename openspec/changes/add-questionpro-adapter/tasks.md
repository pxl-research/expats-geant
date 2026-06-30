## 0. Data model — ValidationHint

- [ ] 0.1 Add `ValidationHint` Pydantic model in `m_shared/models/question.py` with fields `kind: Literal["email","url","phone","number","date","date_time","regex"] | None` and `pattern: str | None`. Add a `model_validator(mode="after")` enforcing that `pattern` is non-null when `kind == "regex"`.
- [ ] 0.2 Add `validation_hint: ValidationHint | None = None` field to `Question`. Add a `model_validator(mode="after")` enforcing that `validation_hint` is `None` for any `type != QuestionType.OPEN_ENDED`.
- [ ] 0.3 Export `ValidationHint` from `m_shared/models/__init__.py`.
- [ ] 0.4 Add unit tests in `tests/test_models.py`: every named `kind` constructs successfully; `kind="regex"` without `pattern` raises; `validation_hint` on a `single_choice` question raises; `validation_hint` is omitted from JSON serialization when `None`.

## 1. Base-class adjustment

- [ ] 1.1 Drop `@abstractmethod` from `SurveyAdapter.import_survey` in `m_shared/adapters/base.py` and add a default body that raises `NotImplementedError(f"{self.__class__.__name__} does not support import_survey()")`, matching the existing pattern for `submit_responses`.
- [ ] 1.2 Confirm the four existing adapter classes (`LimeSurveyAdapter`, `QualtricsAdapter`, `SurveyMonkeyAdapter`, `QTIAdapter`) still implement `import_survey` and advertise `"import"` in their `capabilities()` sets.
- [ ] 1.3 Add a unit test in `tests/test_adapters.py` proving the default raises `NotImplementedError` when subclassed without an override.

## 2. Route guards on import callers

- [ ] 2.1 In `cue_api/routes/surveys.py:225` (`POST /surveys/import`), pre-check `"import" in adapter.capabilities()`. On miss, return `HTTPException(status_code=422, detail=f"Format '{fmt}' does not support file import. Use the API fetch endpoint instead.")`.
- [ ] 2.2 In `shape_api/routes/transforms.py:62` (`POST /transforms/import`), apply the same guard with an equivalent 422 message.
- [ ] 2.3 Add unit tests in `tests/test_questionpro_capabilities.py` covering both 422 paths against the QuestionPro registry entry.

## 2.5. ValidationHint round-trip in existing adapters

- [ ] 2.5.1 **LimeSurvey**: in `import_survey`, parse the `preg` validation attribute on short/long text questions into `ValidationHint`. Map well-known LS regex patterns (if any are bundled) to named kinds; unknown patterns → `ValidationHint(kind="regex", pattern=<orig>)`. In `export_survey`, serialize `ValidationHint` back to `preg`: named kinds use a curated regex per `kind`, `kind="regex"` uses `pattern` verbatim.
- [ ] 2.5.2 **Qualtrics**: in `import_survey`, recognise Qualtrics content-validation entries on TE questions (`ValidEmailAddress` → `kind="email"`, `ValidDate` → `kind="date"`, `ValidNumber` → `kind="number"`, custom regex → `kind="regex"`). In `export_survey`, emit the matching Qualtrics validator block from the `ValidationHint`.
- [ ] 2.5.3 **SurveyMonkey**: in `import_survey`, map `answer_format` on single-textbox questions (`email`, `phone`, `date`, `currency`) to named `kind` values (`currency` → `kind="number"` + `metadata["currency"] = true`). In `export_survey`, set `answer_format` from `ValidationHint.kind`.
- [ ] 2.5.4 **QTI 3.0**: in `import_survey`, map `<restrictions patternMask="...">` to `ValidationHint(kind="regex", pattern=<mask>)`. In `export_survey`, emit `patternMask` from `pattern`; emit a curated regex from named `kind` values that have a standard pattern.
- [ ] 2.5.5 Add round-trip unit tests in `tests/test_adapters.py` for each adapter × each `kind` value, including the "unrecognized regex stays as `kind=regex`" case.
- [ ] 2.5.6 Confirm no regression in the existing import suites — `pytest tests/test_adapters.py tests/test_live_api_import_adapters.py` green.

## 3. QuestionPro adapter implementation

- [ ] 3.1 Scaffold `m_shared/adapters/questionpro.py` with the `QuestionProAdapter` class, constructor signature `__init__(self, api_key: str, datacenter_id: str = "com", *, rollback_on_create_failure: bool = True)`, and a module docstring listing rate limits (300/min per key, 2,400/min per org, 500–20K monthly free-tier quota, 8 KB URL cap) and the "mock all tests" recommendation.
- [ ] 3.2 Implement the v2 base-URL computation: `f"https://api.questionpro.{datacenter_id}/a/api/v2"`. Validate `datacenter_id` against the allowed set on construction.
- [ ] 3.3 Implement an internal `_request(method, path, **kwargs)` helper that injects the `api-key` header, raises `RuntimeError` with the QP response body on non-2xx, and handles `429` with one defensive retry after `Retry-After` seconds (cap at 5 s).
- [ ] 3.4 Implement `capabilities()` returning `{"export", "submit", "create", "api_create"}`.
- [ ] 3.5 Implement `fetch_survey(survey_id)` — `GET /surveys/{id}` + paginated `GET /surveys/{id}/questions?page=&perPage=100` until exhausted, assembled into a `Survey` with sections derived from `static_section_heading` boundaries.
- [ ] 3.6 Implement `export_survey(survey)` — emit a self-describing JSON blob `{"survey": {...}, "questions": [...]}` suitable for offline storage. (Not consumed by a QP importer; it is the symmetric counterpart to `fetch_survey`.)
- [ ] 3.7 Implement `create_survey(survey)` — `POST /users/{user_id}/surveys`, then loop sections + questions emitting `POST /surveys/{id}/questions`. Capture the returned `{questionID, answerID[]}` map into `survey.metadata["questionpro_id_map"]` for later `submit_responses`. Return the new `surveyID` as a string.
- [ ] 3.8 Implement best-effort rollback in `create_survey`: on any failure during the question loop, `DELETE /users/{user_id}/surveys/{survey_id}` and re-raise as `RuntimeError(f"create_survey rolled back after failure on question {n}: {orig}")`. Skip the rollback when `rollback_on_create_failure=False` and re-raise as-is. Log an ERROR with `survey_id`+`user_id` when the rollback `DELETE` itself fails.
- [ ] 3.9 Implement `submit_responses(survey_id, responses)` — `POST /surveys/{survey_id}/responses` with `{"responseSet": [{"questionID": ..., "answerValues": [{"answerID": ..., "value": {"text": ...}}]}]}`. Resolve internal question/choice IDs to QP IDs via `survey.metadata["questionpro_id_map"]`; raise `RuntimeError` with an actionable message when the map is missing.
- [ ] 3.10 Implement the question-type mapping per `design.md` Decision 3. Extract the mapping table into a module-level `_QP_TYPE_TO_INTERNAL` dict; keep it inspectable for tests.
- [ ] 3.11 Implement matrix flattening: each matrix row becomes its own `Question` of the row variant's type, tagged with `metadata["matrix_parent_id"]` (the QP `questionID`), `metadata["matrix_row_index"]`, and `metadata["matrix_variant"]` (e.g. `"matrix_radio"`).
- [ ] 3.12 Implement section structuring on `fetch_survey`: walk the flat question list, and on each `static_section_heading` close the current section and open a new one. The following `static_section_sub_heading` (if any) fills the new section's `description`. Questions accumulate into the open section.
- [ ] 3.13 Map unsupported types (`multiplechoice_maps`, `text_captcha`, `push_to_social`) to `QuestionType.DESCRIPTIVE` with `metadata["questionpro_unsupported_type"]` set, and emit `logger.warning("QuestionPro type %s downgraded to descriptive", qp_type)`.
- [ ] 3.14 Map QP validator-bearing types to `ValidationHint` on import and back on export: `text_email` ↔ `ValidationHint(kind="email")`; `date_time` ↔ `ValidationHint(kind="date_time")`; `calendar` ↔ `ValidationHint(kind="date")`. Customer-configured date display format (when QP exposes one) → `metadata["display_format"]` on import; replayed on export.
- [ ] 3.15 In `create_survey`, when a `Question` carries `validation_hint`, select the corresponding QP type (`text_email`/`date_time`/`calendar`) instead of the default `text_single_row` mapping for `open_ended`.

## 4. Registry & exports

- [ ] 4.1 Register `QuestionProAdapter` in `m_shared/adapters/registry.py` under keys `"questionpro"` and `"qp"`.
- [ ] 4.2 Export `QuestionProAdapter` from `m_shared/adapters/__init__.py` and add a one-line entry to the module docstring's "Available adapters" list.

## 5. Routes — QuestionPro fetch endpoint

- [ ] 5.1 In `cue_api/routes/surveys.py` extend the `POST /surveys/import-from-api` dispatcher to recognise `format == "questionpro"` (or `"qp"`). The request body SHALL contain `survey_id`, `api_token`, and `datacenter_id`. Validate that all three are present; return 400 if any is missing.
- [ ] 5.2 Update `cue_api/models.py` so the import-from-api request model accepts the QuestionPro format string.
- [ ] 5.3 Update the format-list message in the `_get_adapter` 422 (`shape_api/routes/transforms.py:50-53`) to include `questionpro, qp` in the supported list.

## 6. Tests

- [ ] 6.1 Add `tests/test_questionpro_adapter.py` with mocked HTTP fixtures covering: capabilities set, datacenter routing, fetch_survey with sections + questions, export_survey round-trip, create_survey success path, create_survey rollback path, create_survey rollback-disabled path, submit_responses with valid ID map, submit_responses with stale ID map (pre-flight skip + WARNING logs), submit_responses with upstream 4xx per-question (single-shot retry without offending IDs), submit_responses with empty survivor set (raises RuntimeError), submit_responses without ID map (actionable error), pagination on fetch_survey, 429 retry-after handling, question-type mapping for every entry in `_QP_TYPE_TO_INTERNAL`, matrix flattening, unsupported-type downgrade, section construction from static headings, empty `Section.description` skips `static_section_sub_heading` on create, `text_email`/`date_time`/`calendar` round-trip through `ValidationHint`.
- [ ] 6.2 Add `tests/test_questionpro_capabilities.py` covering: registry resolution by both `"questionpro"` and `"qp"`; `POST /surveys/import` returns 422 for `format=questionpro`; `POST /transforms/import` returns 422 for `format=questionpro`; capability set advertised matches the spec.
- [ ] 6.3 Add an opt-in live smoke test in `tests/test_live_api_import_adapters.py` gated on `QUESTIONPRO_API_KEY` env var, exercising `fetch_survey` against a real survey. Skipped in CI.
- [ ] 6.4 Run the full existing suite (`pytest -q`) to confirm no regression on LS/Qualtrics/QTI/SurveyMonkey paths.

## 7. Docs

- [ ] 7.1 Document `QUESTIONPRO_API_KEY=` (empty default) in `.env.example` with a note that it is required only for the opt-in live smoke test.
- [ ] 7.2 Update the `m_shared/adapters/__init__.py` module docstring to include QuestionPro in the "Available adapters" list with a one-line summary and the rate-limit / mocked-tests note.
- [ ] 7.3 Add `scripts/smoke_questionpro.md` — five-minute manual smoke checklist (create a trial account, configure the adapter, fetch a sample survey, push a trivial survey, submit a fake response, verify in the QP admin UI).
