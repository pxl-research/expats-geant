## Context

The reported bug (reorder via chat does nothing visible) traces to a dual
representation of order. Today both `Question` and `Section` carry an
`order: int` field, but every consumer renders by list position:

| Consumer | Orders by |
|---|---|
| UI preview (`survey_preview.html:14`) | list position |
| QTI export (`qti.py:171`) | list position |
| Qualtrics export (flow + BlockElements lists) | list position |
| SurveyMonkey export — questions (`surveymonkey.py:162`) | list position |
| SurveyMonkey export — **sections** (`surveymonkey.py:170`) | **`section.order`** |
| LimeSurvey export — **sections** (`limesurvey.py:340`) | **`section.order`** |
| LimeSurvey export — **questions** (`limesurvey.py:354`) | **`question.order`** |

The field is read in exactly three export sites — all SurveyMonkey/LimeSurvey,
which carry an explicit order slot in their output schema. Everything else
(preview, QTI, Qualtrics, SM questions) already uses list position. Meanwhile
`QuestionPatch` exposes `order`, so `update_question(order=N)` succeeds but only
changes a field that the preview and QTI ignore — a no-op for what the user
sees. There is no operation that moves an item's list position (other than the
delete+add hack).

Adapter import audit (all four build lists in display order already):

- **QTI** — document order.
- **SurveyMonkey** — sorts pages/questions by `position` before building.
- **LimeSurvey** — sorts groups by group order (`:193`) and questions by
  `question_order` (`:227`). These sort raw platform dicts, independent of our
  model field, so they survive field removal untouched.
- **Qualtrics** — builds blocks in survey-flow order (`:122–138`) and questions
  in `BlockElements` order.

## Goals / Non-Goals

- Goals: one source of truth (list position); a real reorder primitive; remove
  the misleading editable `order` knob; keep round-trip ordering correct.
- Non-Goals: a `before_id` / positional-index API (after_id only for now); a
  bulk `reorder_section([ids])` tool; multi-revision history / undo.

## Decisions

- **Drop the field rather than normalize it on save.** Only three export sites
  read it (SM section position, LimeSurvey group/question order); once those
  derive from list index, nothing reads it, so a derived mirror would be dead
  weight — and a vestigial "authoritative-looking" field is exactly the trap
  that caused this bug.
- **Reorder via list-moving operations** (`move_question`, `move_section`) that
  reuse the existing `_insert_after` helper, consistent with `add_section` /
  `add_question` ("use what is already present").
- **`move_question(question_id, after_id=None, section_id=None)`**: `after_id`
  omitted moves to the **front** of the target section (stated explicitly in the
  tool description, since this differs from `add_*` where omitting appends);
  `section_id` moves the question across sections in one call, preserving its
  id and superseding the delete+add hack. **`move_section(section_id,
  after_id=None)`** is included so sections remain reorderable once the field is
  gone.
- **Importers keep their existing raw-platform sorting.** Removing our model
  field only removes the `order=` kwarg at model construction; the sort logic
  over platform data is unaffected.
- Alternatives considered:
  - *(B) Make the `order` field authoritative everywhere* — rejected: most
    invasive (touches all consumers plus every mutation) and sorting on a
    hand-editable int invites duplicate/colliding values.
  - *(C) Prompt-only delete+add* — rejected: leaves the `order` knob live for
    HTTP clients and leaves the misleading field in place.

## Risks / Trade-offs

- An importer relying on the model field for ordering would regress →
  Mitigation: all four audited; none do. Explicit verification tasks included.
- Persisted session drafts contain an `order` key → Mitigation: the models use
  Pydantic's default `extra="ignore"`, so old drafts load fine (key dropped). No
  data migration.
- `move_question`'s `after_id=None` = front diverges from `add_*`'s
  append-on-omit → Mitigation: documented per-tool in the description; add
  `before_id` later only if needed.
- Shared-model change reaches Cue → but `.order` has exactly one reader
  (SM section export) and zero readers in Cue; blast radius is small and
  verified.

## Migration Plan

No data migration (extra ignored). Sequence after `add-granular-survey-mutations`
is archived so its mutation surface is the baseline. Implement in one PR in
dependency order (model → adapters → mutations → patch models → tools →
endpoints → prompt → docs → tests), keeping the suite green at each step.

## Open Questions

- Add a `before_id` (or positional index) for precise arbitrary insertion, or is
  `after_id` (+ omit = front) enough? Recommendation: ship `after_id`; revisit
  only if telemetry shows a need.
