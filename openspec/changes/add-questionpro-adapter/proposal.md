## Why

A customer flagged QuestionPro as an up-and-coming platform we should support. Today our adapter registry covers LimeSurvey, Qualtrics, SurveyMonkey, and QTI; QuestionPro is a recurring ask in vendor evaluations. Adding the adapter unlocks `POST /transforms/create` (Shape) and `POST /surveys/import-from-api` (Cue) for QuestionPro customers, and keeps the platform-bridge surface honest as a competitive parity story.

QuestionPro's v2 REST API (auth via a single `api-key` header, JSON in/out) covers everything we need: fetch survey + questions, create survey + questions, submit responses, and list/export responses. It does **not** expose a downloadable survey-definition file, which forces a small honest adjustment to the `SurveyAdapter` contract: `import_survey(raw: str)` becomes optional, joining `submit_responses`/`create_survey`/`fetch_survey`/`export_responses` in the established opt-in pattern. Adapters advertise what they support via `capabilities()`; the new `QuestionProAdapter` does not advertise `"import"`.

## What Changes

- **Add `validation_hint` field to `Question`** (`m_shared/models/question.py`). Optional `ValidationHint(kind, pattern)` where `kind ∈ {email, url, phone, number, date, date_time, regex}` and `pattern` is regex-only (required when `kind == "regex"`, optional override otherwise). Meaningful only for `open_ended` questions; a model validator SHALL enforce this. Date display format (`YYYY-MM-DD`, `DD/MM/YYYY`, etc.) is a presentation concern and lives in `question.metadata["display_format"]`, NOT on `validation_hint`.
- **Round-trip `validation_hint` in every existing adapter** (LS, Qualtrics, QTI, SurveyMonkey). No adapter handles validation today; each gets new import/export logic to map between its native validator surface (Qualtrics "ValidEmailAddress" content validation, LimeSurvey regex `preg`, SurveyMonkey answer-format `email`/`date`/`phone`/etc., QTI `restrictions` element) and `validation_hint`. Unrecognized platform patterns are preserved in `metadata` as today; the adapter does not invent a hint kind from an unknown regex.
- **Add `m_shared/adapters/questionpro.py`** — new adapter implementing `export_survey`, `fetch_survey`, `create_survey`, `submit_responses`, and `capabilities`. Targets the v2 REST API at `https://api.questionpro.{com|eu|ca|ae|com.au|gov.com|sa.com}/a/api/v2/…`, selected by a `datacenter_id` constructor argument mirroring the Qualtrics adapter shape. Maps `text_email` → `ValidationHint(kind="email")`, `date_time`/`calendar` → `ValidationHint(kind="date")` / `kind="date_time"`.
- **Register the adapter** in `m_shared/adapters/registry.py` under keys `"questionpro"` and `"qp"`.
- **BREAKING (small)**: relax `SurveyAdapter.import_survey()` from `@abstractmethod` to an optional method whose default raises `NotImplementedError`. Other adapters (LS, Qualtrics, QTI, SurveyMonkey) keep their existing `import_survey` implementations and continue to advertise `"import"` in `capabilities()`. Callers SHALL guard the call with a `capabilities()` check, matching the existing pattern for `submit_responses` and `export_responses`.
- **Add capability-discovery scenarios** for QuestionPro: advertises `{"export", "submit", "create", "api_create"}`, NOT `"import"` and NOT `"responses_export"`.
- **Add route guards** for the two callers of `import_survey` that currently invoke it unconditionally:
  - `cue_api/routes/surveys.py:225` (`POST /surveys/import`)
  - `shape_api/routes/transforms.py:62` (`POST /transforms/import`)
  Both SHALL pre-check `"import" in adapter.capabilities()` and return 422 with an actionable message naming the format and the missing capability. Mirrors how `submit` and `responses_export` are already guarded.
- **Add QuestionPro fetch endpoint** path: extend `POST /surveys/import-from-api` (or add a sibling) to dispatch the `questionpro` format using `api_token` + `datacenter_id` + `survey_id`, mirroring the LimeSurvey and Qualtrics fetch shapes.
- **Best-effort rollback** for `create_survey`: on mid-loop failure during the question-creation pass, the adapter SHALL call `DELETE /users/{user-id}/surveys/{survey-id}` and re-raise. Opt-out via constructor arg `rollback_on_create_failure: bool = True`.
- **Question-type mapping** (26 QP types → 6 internal types + validation hints + section structure). Matrix questions flatten into per-row single/multiple choice questions tagged in `metadata` for round-trip; static heading/sub-heading flow into `Section.title`/`Section.description` (and `static_section_sub_heading` is emitted on create only when `Section.description` is non-empty); `static_presentation_text` maps to `QuestionType.DESCRIPTIVE`; unsupported types (`multiplechoice_maps`, `text_captcha`, `push_to_social`) map to `DESCRIPTIVE` with a `metadata.questionpro_unsupported_type` tag and a warn log.
- **`submit_responses` partial-skip behaviour**: on stale ID-map drift, the adapter SHALL pre-filter responses whose internal `question_id` is missing from `survey.metadata["questionpro_id_map"]`, emit structured WARNING logs per skipped response, and submit the survivors. If QP returns a per-question 4xx on submit, the adapter SHALL parse the offending `questionID`, log, and retry the POST once without it. Empty surviving set → raise `RuntimeError` naming the survey. Mixed outcomes → return None silently with WARNINGs visible in the log stream. The `submit_responses(...) -> None` base contract is preserved.
- **Tests** — `tests/test_questionpro_adapter.py` covering import/export/fetch/create/submit against mocked HTTP, plus `tests/test_questionpro_capabilities.py` for the registry + route-guard behaviour. One opt-in live smoke test gated on `QUESTIONPRO_API_KEY` env var, skipped in CI.
- **Docs** — short docstring in the adapter module noting rate limits (300/min per key, 2,400/min per org, 500–20K monthly free quota) and recommending mocked tests during development.

## Impact

- **Affected specs**:
  - `data-models` — ADDED `Question Validation Hint`; MODIFIED `Question Model` to reference the new optional field.
  - `questionnaire-design` — MODIFIED `Platform Adapter Abstraction`, `Adapter Capability Discovery`, `Response Submission via Adapter`, `Stateless Tool API`.
  - `survey-import` — ADDED `Fetch Survey from QuestionPro API`.
- **Affected code**:
  - `m_shared/models/question.py` — new `ValidationHint` Pydantic model + optional `validation_hint` field on `Question` with model_validator enforcing open-ended only.
  - `m_shared/adapters/base.py` — drop `@abstractmethod` from `import_survey`, add default body.
  - `m_shared/adapters/questionpro.py` — new file (~15-20 KB; lands between SurveyMonkey and Qualtrics in size).
  - `m_shared/adapters/limesurvey.py` — round-trip `validation_hint` against LS `preg` regex validators.
  - `m_shared/adapters/qualtrics.py` — round-trip `validation_hint` against Qualtrics content validators (`ValidEmailAddress`, date, etc.).
  - `m_shared/adapters/surveymonkey.py` — round-trip `validation_hint` against SurveyMonkey `answer_format`.
  - `m_shared/adapters/qti.py` — round-trip `validation_hint` to/from QTI `<restrictions>` patternMask.
  - `m_shared/adapters/registry.py` — register `"questionpro"`, `"qp"`.
  - `m_shared/adapters/__init__.py` — export `QuestionProAdapter`, update module docstring.
  - `shape_api/routes/transforms.py` — capabilities guard on `/import`; format-list update in the 422 message.
  - `cue_api/routes/surveys.py` — capabilities guard on `/surveys/import`; dispatch QuestionPro in `/surveys/import-from-api`.
  - `cue_api/models.py` — minor: extend the `import-from-api` request model so `format == "questionpro"` is recognised.
  - `tests/test_models.py` — `ValidationHint` validation and `Question.validation_hint` open-ended-only enforcement.
  - `tests/test_adapters.py` — per-adapter round-trip cases for each `ValidationHint.kind` value.
  - `tests/test_questionpro_adapter.py`, `tests/test_questionpro_capabilities.py` — new.
  - `.env.example` — note the optional `QUESTIONPRO_API_KEY` for the live smoke test.
- **Non-impact**:
  - No new `QuestionType` enum values — date stays as `open_ended` + `validation_hint(kind="date")`.
  - No `update_survey` / round-trip flow — not present today for any adapter; out of scope.
  - No Shape UI changes — adapter is wired through the existing stateless `/transforms/*` endpoints. The Shape UI may surface `validation_hint` later but that is a separate change.
  - No Cue prompt changes for ISO date formatting — flagged as a follow-on; Cue continues to produce strings, QP and the other platforms accept its current output.
