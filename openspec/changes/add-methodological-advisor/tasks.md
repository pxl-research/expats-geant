## 1. System prompt — behavioral directive
- [x] 1.1 Add a two-sentence methodological advisor directive to `build_system_prompt()`
        in `m_chat/conversation.py`: instruct the LLM to raise concerns briefly and ask
        whether choices are intentional; explicitly say not to lecture on minor edits

## 2. Validation engine — new tier-1 checks
- [x] 2.1 Add `social_desirability` check to `_check_question_tier1()`: keyword/phrase
        list similar to `_LEADING_PHRASES` (e.g. "do you regularly", "do you always",
        "do you make sure"); severity `warning`
- [x] 2.2 Add `missing_neutral_option` check to `_check_question_tier1()`: fires for
        `single_choice` questions with an even option count and no option text containing
        neutral-signalling words ("neither", "neutral", "no opinion", "n/a",
        "not applicable"); severity `info`
- [x] 2.3 Add `unbalanced_anchors` check to `_check_question_tier1()`: fires when all
        answer options (≥ 3) lean the same sentiment direction based on a simple positive/
        negative keyword list; severity `warning`
- [x] 2.4 Add `survey_fatigue` survey-level check: add a new
        `_check_survey_tier1(survey) -> list[ValidationIssue]` function counting total
        questions across all sections; fires a `warning` when count exceeds threshold
        (default 30, use a module-level constant); attach to a synthetic
        `question_id="survey"` for the issue
- [x] 2.5 Call `_check_survey_tier1()` from `validate_survey()` alongside existing
        per-question tier-1 checks

## 3. Chat turn wiring
- [x] 3.1 In `execute_chat_turn()`, before applying the survey update, run
        `validate_survey()` (tier-1 only) on the *current* draft to capture the
        baseline issue set
- [x] 3.2 After saving the new draft, run `validate_survey()` (tier-1 only) on the
        *new* draft; diff against baseline to find newly introduced issues
- [x] 3.3 If new issues exist, append a brief advisory note to `text` (the reply):
        surface at most 2 issues, each phrased as "[message] — was this intentional?";
        cap at a single appended paragraph to avoid flooding the reply

## 4. Tests
- [x] 4.1 Unit tests for each new tier-1 check: at least one positive (fires) and one
        negative (does not fire) case per check
- [x] 4.2 Unit test for `_check_survey_tier1`: verify fatigue warning fires above
        threshold and does not fire below it
- [x] 4.3 Integration test for post-update advisory: mock a chat turn that introduces
        a social_desirability issue; verify the advisory note appears in the reply text
- [x] 4.4 Integration test: verify pre-existing issues are NOT re-surfaced in the
        advisory note (baseline diff works correctly)
