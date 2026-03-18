## Context

M-chat has three relevant components:
- `conversation.py` — constructs the system prompt and executes chat turns
- `validation_engine.py` — two-tier validation (deterministic tier-1 + LLM tier-2),
  called on-demand via `/validate`
- `execute_chat_turn()` — calls the LLM, parses the response, saves draft if updated

The question is where scientific validity logic should live.

## Goals / Non-Goals

- Goals:
  - Surface methodological concerns proactively after each survey edit
  - Keep the system prompt focused — behavioral directive only, not a checklist
  - Reuse the existing validation engine rather than duplicating logic
  - Avoid surfacing the same issue repeatedly across turns
- Non-Goals:
  - Full academic methodology audit
  - Blocking edits on validation warnings (advisor role, not gatekeeper)
  - Adding new LLM tier-2 checks in this change (existing batch prompt already covers
    clarity, ambiguity, and cross-question bias; tier-2 extension is future scope)

## Decisions

### System prompt: behavioral directive only

Adding detailed validity rules to the system prompt risks prompt overload — the LLM
already handles draft context, style profile, JSON schema, and output format constraints.
A two-sentence behavioral instruction ("act as a methodological advisor; raise concerns
briefly and ask if intentional; don't lecture on minor edits") sets the right disposition
without competing with structural instructions.

The detailed check logic stays in the validation engine, not the prompt.

### Post-update validation pass in the chat turn

After `survey_updated = True`, `execute_chat_turn()` runs `validate_survey()` on the
new draft (tier-1 only — fast, no extra LLM call) and compares results against the
issues present on the previous draft. Only *newly introduced* issues are surfaced.

This means:
- No redundant repetition of pre-existing issues
- No extra LLM cost per turn
- The advisory note is appended to the LLM's own reply text, so it reads as a natural
  continuation of the assistant message

The previous-draft issue set is computed transiently within the turn (load old draft →
validate → apply update → validate new draft → diff). No issue state is persisted to
disk; the diff is computed fresh each time.

### New tier-1 checks: heuristic, not exhaustive

The four new checks are deliberately conservative heuristics:
- `social_desirability`: keyword-based (phrase list, same pattern as `_LEADING_PHRASES`)
- `missing_neutral_option`: even option count + absence of neutral-signalling words
  ("neither", "neutral", "no opinion", "n/a", "not applicable")
- `unbalanced_anchors`: simple sentiment word lists; fires only when *all* options lean
  one direction and there are ≥ 3 options
- `survey_fatigue`: total question count across sections > configurable threshold (default 30)

These are warning-severity only. They will produce false positives in some cases; the
conversational framing ("was this intentional?") is the correct response to a warning,
not an error.

## Risks / Trade-offs

- **Advisory noise**: if the LLM makes multiple structural changes in one turn, several
  issues could surface at once. Mitigated by only surfacing new issues (diff approach)
  and capping the advisory note to the top 2 issues per turn.
- **False positives from heuristics**: the keyword-based checks will occasionally fire
  on legitimate questions. The "was this intentional?" framing handles this gracefully.
- **Prompt length**: appending advisory notes to replies adds a few lines to the
  conversation history over time. With `_LAST_N_MESSAGES = 20` this is acceptable.
