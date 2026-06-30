## Context

QuestionPro is a SaaS survey platform with a JSON-only v2 REST API. A customer flagged it as up-and-coming during a vendor evaluation. We have four adapters today (LimeSurvey, Qualtrics, SurveyMonkey, QTI 3.0) and a stable `SurveyAdapter` contract; the question is whether QuestionPro fits the contract or forces a contract change.

Two facts shape the design:

1. **No native survey-definition file format.** QuestionPro stores surveys server-side; customers don't download QSF/LSS/XML equivalents. The platform-bridge path is therefore API-only: fetch via `GET /surveys/{id}` + `GET /surveys/{id}/questions`, create via `POST /users/{user-id}/surveys` followed by a per-question `POST /surveys/{id}/questions` loop. This is a structural difference from the four existing adapters, all of which parse a downloadable file.

2. **Rich question-type vocabulary (26 types).** Most map cleanly to our 6-type internal model (`single_choice`, `multiple_choice`, `open_ended`, `ranking`, `slider`, `descriptive`). Matrix questions (6 variants) and 3 exotic types (maps/captcha/social-share) need explicit decisions.

## Goals / Non-Goals

**Goals**
- Add a `QuestionProAdapter` that supports `export_survey`, `fetch_survey`, `create_survey`, `submit_responses`, and `capabilities()`.
- Make the `SurveyAdapter` base class honest about which methods are optional (move `import_survey` out of `@abstractmethod`).
- Keep the changes for the existing four adapters strictly additive at the contract level (their `import_survey` implementations are untouched; they continue to advertise `"import"`).
- Cover all 26 QuestionPro question types end-to-end (mapped, flattened, or downgraded), with no silent data loss.

**Non-Goals**
- No `update_survey` / round-trip flow. None of our adapters support this today, and no consumer calls one. Re-visit when a real use case appears.
- No `responses_export` for QuestionPro — they don't have an admin-UI file importer to target.
- No new internal model fields. QuestionPro's matrix and exotic types are absorbed via the existing `metadata` escape hatch on `Question` and via flattening for matrix.
- No QuestionPro UI affordances in Shape — the adapter is wired through the existing stateless `/transforms/*` endpoints. UI work, if any, comes later.

## Decisions

### Decision 1: `import_survey` becomes optional on the base class

`base.py` removes `@abstractmethod` from `import_survey` and adopts the same default body pattern as `submit_responses`, `create_survey`, `fetch_survey`, and `export_responses`:

```python
def import_survey(self, raw: str) -> Survey:
    raise NotImplementedError(
        f"{self.__class__.__name__} does not support import_survey()"
    )
```

QuestionPro's adapter does not override it and does not include `"import"` in `capabilities()`. The two route consumers that currently call `import_survey` unconditionally (`cue_api/routes/surveys.py:225`, `shape_api/routes/transforms.py:62`) are tightened to pre-check the capability and return 422 with an actionable message — matching the existing guard pattern for `submit_responses` (`cue_api/routes/surveys.py:407`) and `export_responses` (`:497`).

**Alternatives considered**

- Have QuestionPro implement `import_survey` by parsing a JSON dump we invent for it. Rejected: we'd be defining a file format solely to satisfy the contract, with no real user-facing input to put in it.
- Have QuestionPro's `import_survey` raise inline while keeping `@abstractmethod` on the base. Rejected: it would lie about the contract — the base says every adapter implements import, but one of them doesn't. The optional-method pattern already exists in the codebase for exactly this case.
- Add a separate `import_capable` flag. Rejected: `capabilities()` already serves this purpose; adding a parallel mechanism is duplication.

### Decision 2: Two-step create with best-effort rollback (default on)

`create_survey(survey)` performs:

1. `POST /users/{user_id}/surveys` with metadata → receive new `surveyID`.
2. For each section: emit `static_section_heading` and `static_section_sub_heading` via `POST /surveys/{id}/questions` (preserves section structure on QP's side, since QP has no first-class section concept).
3. For each question: `POST /surveys/{id}/questions` with type-mapped payload.

On any failure during steps 2–3, the adapter calls `DELETE /users/{user_id}/surveys/{survey_id}` and re-raises the original exception with a `RuntimeError(f"create_survey rolled back after failure on question {n}: {orig}")`. Constructor argument `rollback_on_create_failure: bool = True` makes this default. Power users who want to inspect the partial survey can pass `False`.

**Alternatives considered**

- No rollback. Rejected: a partial survey on the customer's QuestionPro account is worse than the absence of a survey, and `DELETE` is available and idempotent.
- Two-phase commit / staging area. Rejected: their API has no transaction concept; over-engineering for a low-frequency operation.
- Rollback off by default. Rejected: leaves orphan state by default, which is the wrong UX.

### Decision 3: Question-type mapping

The 26 QP types map to the 6 internal `QuestionType` values plus the `Section` shape:

| QuestionPro type | Internal target | Notes |
|---|---|---|
| `multiplechoice_radio` | `single_choice` | direct |
| `multiplechoice_dropdown` | `single_choice` | metadata: `display: "dropdown"` |
| `multiplechoice_image_radio` | `single_choice` | metadata: `image: true` |
| `multiplechoice_thumbs_up_down` | `single_choice` | two-option Yes/No |
| `multiplechoice_checkbox` | `multiple_choice` | direct |
| `multiplechoice_image_checkbox` | `multiple_choice` | metadata: `image: true` |
| `text_single_row` | `open_ended` | direct |
| `text_multiple_row` | `open_ended` | metadata: `display: "multiline"` |
| `text_email` | `open_ended` | metadata: `validation: "email"` |
| `numeric_slider` | `slider` | `min_value`/`max_value`/`step` |
| `matrix_*` (6 variants) | flattened per row | one internal question per matrix row; metadata: `matrix_parent_id`, `matrix_row_index`, `matrix_variant` |
| `rank_order_dropdown` | `ranking` | direct |
| `rank_order_drag_drop` | `ranking` | metadata: `display: "drag_drop"` |
| `date_time` / `calendar` | `open_ended` | metadata: `validation: "date"` (no new type) |
| `static_presentation_text` | `descriptive` | direct |
| `static_section_heading` | (Section.title) | opens a new `Section` |
| `static_section_sub_heading` | (Section.description) | fills the current section's description |
| `multiplechoice_maps` | `descriptive` | warn log; metadata: `questionpro_unsupported_type: "multiplechoice_maps"` |
| `text_captcha` | `descriptive` | warn log; metadata: `questionpro_unsupported_type: "text_captcha"` |
| `push_to_social` | `descriptive` | warn log; metadata: `questionpro_unsupported_type: "push_to_social"` |

**Alternatives considered for matrix**

- Skip matrix questions entirely. Rejected: customers using matrices would silently lose data on import.
- Add a `matrix` type to the internal model. Rejected: matrix is genuinely platform-specific in its rendering; the data shape is N rows × M columns, which flattens cleanly. Adding a new internal type forces every other adapter to deal with it.
- Store matrix as a single `Question` with all rows in `metadata`. Rejected: defeats the point of having a typed model; downstream consumers (validation, suggestion, Cue answering) would need special cases.

The flattening strategy preserves data for round-trip via metadata anchors and lets the rest of the pipeline treat matrix rows as ordinary single/multiple-choice questions. Round-trip back to QuestionPro (a future feature) can reconstruct the matrix from the `matrix_parent_id` clustering.

### Decision 4: Datacenter routing via constructor argument

Constructor signature mirrors Qualtrics:

```python
QuestionProAdapter(api_key: str, datacenter_id: str = "com")
```

where `datacenter_id` is one of `"com"`, `"eu"`, `"ca"`, `"ae"`, `"com.au"`, `"surveyanalytics.com"`, `"gov.com"`, `"sa.com"`. The base URL is computed as `f"https://api.questionpro.{datacenter_id}/a/api/v2"`. The registry threads this through via the `**kwargs` that `get_adapter` already accepts.

### Decision 5: Capability set advertised

```python
def capabilities(self) -> set[str]:
    return {"export", "submit", "create", "api_create"}
```

Notably absent:
- `"import"` — no native file format to parse.
- `"responses_export"` — no admin-UI file importer to target.

Existing capability strings are sufficient; no new string introduced.

### Decision 6: Live API testing is opt-in

All adapter tests SHALL mock the HTTP layer (`responses_mock` or `httpx_mock`). A single integration test in `tests/test_live_api_import_adapters.py` SHALL be gated on `QUESTIONPRO_API_KEY` env var and skipped in CI. The free-tier monthly quota (500 calls/month for trial accounts) makes loose live testing infeasible; the mocked tests cover all paths.

### Decision 7: ValidationHint on the Question model

QuestionPro's `text_email`, `date_time`, and `calendar` types — and the equivalent date/email/phone validators across Qualtrics, LimeSurvey, and SurveyMonkey — surface a cross-platform need that is currently absorbed into per-adapter `metadata` dicts with no shared key. This change introduces a typed first-class field on the `Question` model:

```python
class ValidationHint(BaseModel):
    kind: Literal["email", "url", "phone", "number", "date", "date_time", "regex"] | None = None
    pattern: str | None = None  # required when kind=="regex"; optional override otherwise

# on Question:
validation_hint: ValidationHint | None = None
```

A model validator SHALL enforce that `validation_hint` is meaningful only when `question.type == "open_ended"`; setting it on choice/ranking/slider/descriptive questions SHALL raise. The validator SHALL also enforce that `pattern` is non-null when `kind == "regex"`.

The seven `kind` values are the intersection of practical validators across the platforms we ship adapters for, plus `"regex"` as a typed escape hatch. Length constraints (`min_length`, `max_length`) are deliberately omitted from v1; they can be added if a real consumer surfaces.

**Date display format goes in `metadata`, not on the hint.** A regex `pattern` matches text; a format string (e.g. `YYYY-MM-DD`, `DD/MM/YYYY`) is a presentation template. They are semantically distinct, and format-string dialects (LDML vs. strftime vs. Moment.js) are not portable across platforms. Customer display preferences captured on import are stashed at `question.metadata["display_format"]` and replayed on export by adapters whose target platform exposes a format setting. Internal exchange canonicalizes dates to ISO 8601.

**Why typed rather than regex-only**:
- Round-tripping platform-native semantic validators (QP `text_email`, Qualtrics `ValidEmailAddress`, SurveyMonkey `email`) requires preserving the *intent*, not just a regex that happens to match emails. Recovering "this is an email" from an arbitrary email regex is brittle.
- Downstream consumers (Cue answer generation, the validation engine, future analytics) benefit from semantic labels they can reason about. A bare regex is opaque to LLMs.

**Per-adapter round-trip**:
- **QuestionPro**: `text_email` ↔ `kind="email"`, `date_time` ↔ `kind="date_time"`, `calendar` ↔ `kind="date"`. Other QP types map cleanly to existing `QuestionType` values.
- **Qualtrics**: Content validation on TE questions (`ValidEmailAddress`, `ValidDate`, etc.) round-trips to/from the matching `kind`. Custom regex content validation maps to `kind="regex"` with the pattern preserved.
- **LimeSurvey**: `preg` validation strings map to `kind="regex"`. Well-known regex patterns LS bundles (if any) map to `kind="email"` / `"date"` etc.; unrecognised patterns stay as `kind="regex"`.
- **SurveyMonkey**: `answer_format` field on text inputs maps to the matching `kind` (`email`, `phone`, `date`, `currency` → `kind="number"`+`metadata["currency"]=true`).
- **QTI 3.0**: `<restrictions>` patternMask maps to `kind="regex"` with the pattern preserved.

Unrecognised platform patterns SHALL be preserved verbatim in adapter-specific `metadata` keys (existing convention) AND the corresponding `validation_hint` SHALL remain null. The adapter SHALL NOT guess a `kind` from an unfamiliar regex.

### Decision 8: Date is a validation hint, not a new QuestionType

QuestionPro (and the other platforms) treat date inputs as distinct types in their UI. The temptation is to mirror that with a `QuestionType.DATE`. We deliberately do not:

- Date answers are structurally strings (or ISO date strings). The `Question` model already distinguishes "answer is a string" via `open_ended`. The "this string is a date" constraint is exactly what `ValidationHint(kind="date")` was added for.
- Adding a new `QuestionType` ripples to every adapter, every UI surface, and every prompt template. The validation-hint approach localises the change to text-input rendering and platform serialization.
- If a future need surfaces (date pickers in Shape UI, date-aware Cue answering with calendar widgets), promoting `kind="date"` to a first-class type is a clean refactor — every consumer is already branching on `validation_hint` anyway.

**Cue prompt update for ISO 8601 formatting is a follow-on**, not in this proposal. Cue currently emits string answers that QuestionPro accepts; making the LLM aware of `validation_hint.kind == "date"` and emitting strict ISO 8601 is a separate change to `cue_api/rag_pipeline.py`.

### Decision 9: submit_responses partial-skip behaviour

Stale ID maps in `survey.metadata["questionpro_id_map"]` are handled with graceful degradation, not silent reconciliation:

1. **Pre-flight filter**: walk the inbound `responses` list. Any response whose `question_id` is missing from the local map is dropped from the submit payload and logged at WARNING with `{response_id, question_id, reason: "local_id_map_miss"}`.
2. **POST the survivors**: a single `POST /surveys/{id}/responses` with whatever passed pre-flight.
3. **Per-question 4xx handling**: if QP returns a structured error naming specific `questionID`s, parse, log each at WARNING with `reason: "upstream_id_not_found"`, and retry the POST once without those questions. Only one retry.
4. **Empty survivor set** → raise `RuntimeError(f"All responses skipped due to stale ID map for survey {survey_id}; re-fetch and resubmit")`.
5. **Partial success** → return `None` silently. Operators see the skips via WARNING logs.

This keeps the `submit_responses(...) -> None` base contract unchanged across all adapters — no return-type evolution. The skip list surfaces through structured logs, not through return values; the route layer does not need to know about it for v1. If a real consumer needs programmatic access to the skip list later, we add a structured side-channel (e.g. `survey.metadata["last_submit_skipped"]`) at that point.

**Why not re-fetch first** (the rejected alternative): re-fetching the survey before every submit hides drift. A customer's intent is to record the response; silent reconciliation would absorb missing-question drift without surfacing it, masking the kind of bug that materialises three months later as "we lost data on field X." Fail-loud-but-graceful is the right default.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `import_survey` becoming optional breaks an unknown caller that doesn't check capabilities. | Grep already confirmed only two callers, both in routes. Both are updated to pre-check. Tests cover the 422 path. |
| Matrix flattening loses visual grouping on round-trip back to a non-QP platform. | Acceptable for v1 — matrix is not currently round-tripped anywhere. The `metadata.matrix_parent_id` anchor lets a future round-trip reconstruct. |
| Mid-create-loop rollback `DELETE` itself fails (race, auth blip), leaving an orphan survey. | Log a structured ERROR including the orphan `survey_id` and `user_id` so an operator can clean up manually. The original exception is preserved as the cause. |
| Rate limit hit during a long create-survey loop (300/min). | Loop has natural pacing from network latency, but defensive sleep on `429` with one retry. Multi-organisation aggregate cap (2,400/min) is unlikely to bite. |
| Free-tier 500/month quota burns out during dev. | All tests mock HTTP. Live test is opt-in and explicitly skipped in CI. Documented in adapter module docstring. |
| QuestionPro changes their v2 API shape underneath us. | Same risk applies to every adapter; standard mitigation is the live smoke test catching breakage early. |
| Adding `validation_hint` to four existing adapters silently changes their import output (existing tests may not exercise validators). | Each adapter gets new round-trip tests covering every `kind` value. Existing import tests are reviewed for regressions before the change lands. The field is optional (default `None`) so adapters that don't recognize a platform validator continue producing the same `Question` shape as today. |
| Adapter authors guess `kind="email"` from arbitrary platform regex patterns and misclassify. | Explicit policy in Decision 7: adapters SHALL NOT infer a `kind` from an unknown regex. They use `kind="regex"` and preserve the pattern verbatim. Per-adapter tests cover the "unknown regex stays as `kind="regex"`" path. |

## Migration Plan

No data migration. The base-class change is source-compatible for the existing four adapters — they continue to implement `import_survey`, the method just isn't `@abstractmethod` anymore. The route-guard additions are pure additions; existing callers that supply a format with `"import"` in capabilities (lss, qsf, qti, sm) see no behaviour change.

Rollout order:

1. Land the base-class + route-guard change in one PR with the new adapter (single change ID).
2. Existing test suite must pass green (proves no regression in LS/Qualtrics/QTI/SM paths).
3. New `tests/test_questionpro_adapter.py` proves the new adapter.
4. Optional: a manual smoke against a real QuestionPro trial account by the implementer, documented in `scripts/smoke_questionpro.md`.

Rollback: revert the PR. The change is self-contained (one new module + minor edits to two routes and the base class).

## Open Questions

All four open questions raised during scoping have been resolved:

- ~~Section heading sub-heading emission when empty~~ → folded into Decision 1 (skip when `Section.description` is empty).
- ~~`validation_hint` field shape~~ → resolved by Decision 7 (typed `kind` + optional regex `pattern`; date format in `metadata`).
- ~~Date as type vs. hint~~ → resolved by Decision 8 (validation hint, no new `QuestionType`).
- ~~ID-map staleness handling~~ → resolved by Decision 9 (partial-skip + WARNING logs; never silent reconciliation).

Remaining items intentionally deferred from v1:

- **Length constraints (`min_length`, `max_length`) on `ValidationHint`** — common across Qualtrics and SurveyMonkey, but no internal consumer needs them today. Add when a real use case surfaces.
- **`validation_hint` on non-open-ended questions** — locked to `open_ended` for v1 via a model validator. Could be lifted for choice-with-other questions if needed.
- **Cue ISO 8601 date-formatting prompt** — `cue_api/rag_pipeline.py` does not currently branch on `validation_hint`. A follow-on change SHOULD teach the answer-generation prompt to emit ISO 8601 when `validation_hint.kind ∈ {"date", "date_time"}`. Not blocking; QP accepts Cue's current free-text dates.
- **Shape UI surfacing of `validation_hint`** — the form-editor in Shape UI has no validation-hint affordance yet. Add when the model field has real consumers.
