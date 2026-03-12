# Change: Add Methodological Advisor Behaviour to M-Chat

## Why

M-chat currently helps users design questionnaires but does not proactively challenge
methodological choices. The validation engine runs on-demand via `/validate`, but a
user working in the chat interface receives no unprompted feedback on scientific quality.
Leading questions, unbalanced scales, or socially desirable wording can slip through
unnoticed unless the user explicitly asks.

The goal is for m-chat to behave like a knowledgeable collaborator that notices potential
issues and asks "was this intentional?" — without lecturing on every keystroke.

## What Changes

1. **System prompt** — a two-sentence behavioral directive added to `build_system_prompt()`
   instructing the LLM to act as a methodological advisor: raise concerns briefly and
   ask whether choices are intentional; do not lecture unprompted on minor edits.

2. **Validation engine — new tier-1 checks** added to `validation_engine.py`:
   - `social_desirability`: question text implies a virtuous or socially expected answer
     (e.g. "do you regularly…", "do you always…")
   - `missing_neutral_option`: single-choice scale with an even number of options and
     no detectable neutral label — forces a directional choice
   - `unbalanced_anchors`: all answer option texts lean the same sentiment direction
     (all positive or all negative), suggesting a biased scale
   - `survey_fatigue`: total question count across all sections exceeds a threshold
     (default: 30 questions); survey-level check, not per-question

3. **Chat turn wiring** — after `survey_updated = True` in `execute_chat_turn()`, run
   `validate_survey()` and, if any `warning` or `error` issues are new since the last
   turn, append a short advisory note to the LLM reply:
   *"I also noticed: [issue message]. Was that intentional?"*
   Issues that were already present before the edit are not re-surfaced.

## Impact

- Affected specs: `questionnaire-design` (ADDED requirement)
- Affected code: `m_chat/conversation.py`, `m_chat/validation_engine.py`
- No breaking changes; `/validate` endpoint, existing tier-1/tier-2 checks, and all
  other engines are unchanged
- No UI changes required — advisory notes appear in the existing chat reply
