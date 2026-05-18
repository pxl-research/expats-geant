# Tasks

## 1. LLM client — expose tool calls from a completion

- [x] 1.1 In `m_shared/llm/client.py`, add a new method
  `create_completion_full(self, messages, tools=None, **kwargs)` that returns
  the entire `response.choices[0].message` object (or a small typed dataclass
  with `content: str | None` and `tool_calls: list`). Reuse the existing
  `_inject_thinking`, `_retry_with_backoff`, `extra_headers`, and
  `temperature` logic.
- [x] 1.2 Leave `create_completion(...)` (the content-only method) untouched.
- [x] 1.3 Unit test: a mocked completion that returns content only → method
  returns a result with `content` populated and no tool calls.
- [x] 1.4 Unit test: a mocked completion that returns a tool call → method
  returns a result with the tool call surfaced (function name, arguments,
  call ID).

## 2. Shape — tool definition and dispatcher

- [x] 2.1 Create `shape_api/tools.py` with:
  - The OpenAI-style tool schema for `get_full_survey` (function with no
    parameters, with a description explaining it returns the full current
    draft).
  - A `dispatch_tool_call(name, arguments, base_path, session_id) -> str`
    helper that returns the JSON string of the draft for
    `name == "get_full_survey"` and raises `ValueError` for unknown names.
- [x] 2.2 Unit test: dispatcher returns the on-disk draft JSON for an existing
  session.
- [x] 2.3 Unit test: dispatcher returns a sentinel JSON (`{}` or
  `{"survey": null}` — pick and document) when the session has no draft yet.
- [x] 2.4 Unit test: dispatcher raises `ValueError` for an unknown tool name.

## 3. Shape — summary enrichment

- [x] 3.1 In `shape_api/suggestion_engine.py`, modify `compact_survey_summary`
  to format sections as `Section [<sec_id>]: <title>` and questions as
  `- [<q_id>] <text>`. Preserve indentation. No other fields.
- [x] 3.2 Unit test: a survey with two sections, three questions each → the
  summary string contains every section ID and every question ID exactly once,
  and does **not** contain `answer_options`, `type`, `required`, or any
  metadata keys.
- [x] 3.3 Audit: confirm `compact_survey_summary` is only called from the
  conversation system prompt path (not by any other caller that depends on
  the old format). Update any callers that rely on the old format.

## 4. Shape — tool-call loop in `execute_chat_turn`

- [x] 4.1 In `shape_api/conversation.py`, refactor `execute_chat_turn` to use
  a loop with at most 3 iterations (named constant `MAX_TOOL_CALL_ITERATIONS`).
- [x] 4.2 On each iteration: call the LLM via the new full-message method,
  passing the `[get_full_survey]` tool definition.
- [x] 4.3 If the response message has tool calls: append the assistant tool-call
  message to the in-memory messages list; dispatch each tool call; append a
  `role: "tool"` message per call with `tool_call_id` + the result; continue.
- [x] 4.4 If the response message has no tool calls: exit the loop; parse the
  message's `content` for the `<survey_update>` tag using the existing
  regex; on match, save the draft (existing path); return the assistant text
  and `survey_updated` flag.
- [x] 4.5 If the loop reaches the cap: treat the last assistant message as the
  final response; log a `WARNING` with session ID, iteration count, and the
  count of tool calls in the final message; continue with `<survey_update>`
  parsing of the last assistant content (defensive — usually empty).
- [x] 4.6 Log an `INFO`-level structured entry for each successful tool call
  including session ID and an iteration counter.
- [x] 4.7 When a `<survey_update>` block is applied and the loop never invoked
  `get_full_survey` on this turn, log a `WARNING` so we can monitor
  non-compliance.

## 5. Shape — prompt update

- [x] 5.1 In `shape_api/conversation.py:build_system_prompt`, add a paragraph
  immediately after the existing schema section that:
  - tells the LLM the summary above intentionally omits fields,
  - instructs the LLM to call `get_full_survey` before emitting any
    `<survey_update>`,
  - explains that the tool returns the authoritative current draft and that
    unchanged fields **must** be copied verbatim from the tool result.
- [x] 5.2 Keep the existing soft instruction about "only include
  `<survey_update>` when proposing structural changes."
- [x] 5.3 Do **not** add language asserting the rule is enforced server-side
  (it is not).

## 6. Tests — integration

- [x] 6.1 Mock LLM scripted to return a tool call on iteration 1 and a
  `<survey_update>` on iteration 2 → assert draft is saved with the LLM's
  posted survey content and `survey_updated=True`.
- [x] 6.2 Mock LLM scripted to return text only on iteration 1 (no tool call,
  no `<survey_update>`) → assert single LLM call, no dispatch, no draft
  change, `survey_updated=False`.
- [x] 6.3 Mock LLM scripted to return a `<survey_update>` on iteration 1
  without calling the tool → assert draft is saved (soft enforcement) **and**
  a `WARNING` is logged indicating non-compliance.
- [x] 6.4 Mock LLM scripted to loop tool calls indefinitely → assert the loop
  stops at the cap, a `WARNING` is logged, and the turn returns gracefully.
- [x] 6.5 Reproduce the clobber scenario (`/tmp/test_chat_clobber.py` shape):
  PUT a survey with carefully-crafted `answer_options`, run a chat turn where
  the mocked LLM emits a `<survey_update>` that copies the JSON returned from
  the mocked `get_full_survey` verbatim → assert the user's `answer_options`
  are preserved through the round-trip.

## 7. Documentation

- [x] 7.1 Update `docs/SHAPE_API.md`: under `POST /chat/{session_id}`, add a
  one-paragraph note describing the tool-call loop and the fact that the LLM
  loads the full draft on edit turns. Do not document the prompt wording.
- [x] 7.2 If a tunable `MAX_TOOL_CALL_ITERATIONS` is exposed via env var, add
  it to `.env.example` and `docs/DEPLOYMENT.md`. Otherwise skip.

## 8. Validation

- [x] 8.1 `openspec validate add-chat-turn-survey-tool-load --strict` clean.
- [x] 8.2 Full test suite green (`pytest`).
- [ ] 8.3 Manual smoke against the deployed Gemini-flash gateway: edit a
  small survey via PUT, ask a follow-up question in chat, verify that the
  edits are preserved. Repeat 5–10 times and record how often the LLM skips
  the tool call (baseline for the escalation decision).
- [ ] 8.4 Capture the manual-smoke counts in the change folder (e.g. an
  appendix in `design.md` open-questions section) before archiving.
