# Design: Chat-turn survey draft loaded via LLM tool call

## Context

The current chat turn pipeline (`shape_api/conversation.py:93-151`, called from
`shape_api/routes/chat.py:283`):

1. Loads the on-disk draft via `load_draft_survey`.
2. Builds the system prompt with `compact_survey_summary(draft)`. The summary
   contains **only** the survey title, section titles, and question text.
3. Sends the conversation history and a new user message to the LLM.
4. Parses any `<survey_update>...</survey_update>` block in the LLM response.
5. If present, constructs a `Survey` from the JSON and overwrites the draft.

Steps 1 and 2 are the load step; step 4–5 is the save step. The user's PUT is
visible at step 1 (fresh from disk) and immediately discarded at step 2 (the
projection drops everything except text). When the LLM is then required to
output a complete survey (per the system prompt at `conversation.py:89`), it
has no choice but to invent every dropped field. Step 5 then makes that
invention authoritative.

The integrator's report — "PUT returns 200, edits are gone on the next GET"
— is fully explained by this flow. A reproducer (`/tmp/test_chat_clobber.py`
during the investigation session) confirmed it deterministically.

The `m_shared/llm/client.py` (`LLMClient`) already accepts a `tools_list` in its
constructor and forwards it to OpenRouter's chat-completions API on both
streaming and non-streaming calls (`client.py:114`, `client.py:138`). The only
gap is that `create_completion(...)` returns only `response.choices[0].message.content`
and discards `message.tool_calls` (`client.py:144`). The infrastructure for
tool-calling exists; we are not building it from scratch.

## Goals / Non-Goals

**Goals**
- Stop the silent clobber of user PUT edits during the next chat turn.
- Keep the chat-turn HTTP contract unchanged (no breaking changes to callers).
- Establish the smallest credible tool-calling foundation we can extend later.
- Make compliance with the new flow **observable**: when the LLM skips the tool,
  we want to know.

**Non-Goals**
- Multi-tool edit surface (`edit_question`, `add_question`, `remove_question`,
  …). Deferred. This proposal is the foundation that makes such a surface a
  small follow-up rather than a green-field rewrite.
- JSON Patch / merge-patch output contract from the LLM. Deferred.
- MCP server. Overkill for an in-process tool we already own.
- Cross-session tool calls or tools that touch other users' data. Out of scope.
- Reduction of the prompt's existing methodological-advisor copy. Independent
  concern.

## Decisions

### Decision 1: Single tool — `get_full_survey` — not a tool family

We could have introduced `edit_question`, `add_question`, `remove_question`,
`edit_section`, etc. in one go. We deliberately did not.

*Why one tool:*
- It fixes the specific clobber path (the LLM now sees the data it must
  preserve) with the minimum number of moving parts.
- It lets us learn whether Gemini-flash-class models reliably call the tool
  when prompted to. If adoption is poor, the multi-tool design would have been
  built on sand.
- The existing `<survey_update>` save path is preserved, so any auxiliary code
  (UI listeners, tests, integration scripts) that depends on it keeps working.

*What we give up:* the LLM still has to copy unchanged fields back when it
emits `<survey_update>`. Flash-tier models drift on long copy tasks. This is the
honest residual risk; see Risks below.

*Decision rule for the follow-up:* if structured logging shows the LLM emits
`<survey_update>` without a prior `get_full_survey` in more than a small share
of edit turns, or if pilot users continue to report missing fields after this
ships, we escalate to a multi-tool patch surface.

### Decision 2: Tool produces the **on-disk** state, not the in-flight summary

`get_full_survey` reads `draft_survey.json` at the moment of the tool call. It
does **not** consult any cached object built earlier in the turn. This is
intentional: if a parallel write (e.g. a concurrent PUT, unlikely but
possible) lands between the system prompt build and the tool call, the LLM
sees the newer state. The cost is one extra disk read per tool call, which is
trivial.

### Decision 3: Loop cap = 3 iterations

The tool-call loop iterates at most 3 times within a single chat turn. In
practice we expect:
- Pure Q&A turn: 1 iteration (LLM responds text-only, no tool call). Loop
  exits.
- Edit turn: 2 iterations (call → tool → response with `<survey_update>`).
  Loop exits.
- Pathological loop: capped at 3. We treat the 3rd response as final regardless
  of tool calls; remaining tool calls (if any) are ignored and a warning is
  logged.

The cap is defensive, not a normal exit condition. Configurable via a constant
in `shape_api/conversation.py` so we can raise it if a legitimate use case
emerges.

### Decision 4: Prompt instruction is **soft**, server applies anyway

The system prompt tells the LLM to call `get_full_survey` before emitting
`<survey_update>`. We do **not** server-side reject an update that arrives
without a prior tool call. Reasons:
- A hard reject would break any legitimate "tiny edit" the LLM does without
  thinking it needs the full state — and probably teach future maintainers
  that the rule is enforced when in fact it cannot be enforced perfectly
  (the LLM is the thing we're trying to constrain).
- Soft enforcement + structured logging gives us the data to decide whether to
  ratchet to a hard contract (Decision rule from Decision 1).
- The cost of a soft instruction failing is the *current* clobber risk, which
  is what we're trying to reduce — not amplify. Falling back to today's
  behaviour on misses is acceptable.

We log a `WARNING` level message including session ID, turn iteration, and
whether the update contained changes that look syntactically substantial (e.g.
new question IDs not present in the prior summary).

### Decision 5: ID-only summary enrichment

The enriched summary contains:
- `Survey: <title>`
- `  Section [<sec_id>]: <title>`
- `    - [<q_id>] <text>`

It deliberately does **not** include question types, answer options, required
flags, min/max, metadata, or descriptions. Two reasons:
- The summary's job becomes "give the LLM a stable handle to refer to elements
  in conversation." Anything beyond that is leakage of the data the tool is
  there to provide.
- Bigger summaries are more expensive per turn (every turn, including pure
  Q&A). Concentrating richness behind the tool call keeps per-turn cost in
  line with today's footprint.

### Decision 6: Observability through structured logs, not the audit ledger

We use Python's `logging` (`shape_api/conversation.py` logger) at `INFO` level
for each successful tool call, `WARNING` for an `<survey_update>` without a
prior tool call, and `WARNING` for hitting the loop cap.

We deliberately **do not** extend the `m_shared/utils/audit.py` `AuditEventType`
enum or write into the audit ledger. The audit ledger is a privacy-and-
transparency surface for Cue respondents (`audit-compliance` capability,
"Session Audit Trail" requirement); Shape's chat turns are an administrator-
side authoring loop and are not on the user-transparency path. Mixing the two
would dilute both. If we later need formal observability metrics, those go
through the `add-mlflow-observability` initiative, not the audit ledger.

### Decision 7: Conversation history must include tool calls and tool results

When the LLM emits a tool call, both the assistant message containing the
call **and** the role=`tool` response containing the result are appended to
the in-memory conversation list for the rest of that turn's loop. The
canonical persisted conversation history (the on-disk `conversation.jsonl`
written by `append_message` in `shape_api/routes/chat.py:292-293`) continues
to record only the final assistant text + the user message, matching today's
behaviour. The tool exchange is ephemeral to the turn.

*Why ephemeral:* persisting tool calls into the user-visible history would
clutter the UI and tempt future turns to "see" old tool outputs that may be
stale. Each turn re-derives state from disk; that property should not change.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| LLM ignores the prompt instruction and emits `<survey_update>` without calling the tool, falling back to today's clobber | Log warnings; pilot feedback loop; escalate to multi-tool surface if it remains common |
| LLM calls `get_full_survey` but still drifts when copying unchanged fields | Smaller than today (it now has the source to copy from), but real; same escalation path |
| Loop cap reached due to LLM spamming tool calls | Cap at 3; log warning; turn still returns its best assistant message |
| One extra LLM round-trip on edit turns adds latency | ~1 s on Gemini-flash; only on edit turns (not Q&A); user-visible chat already shows a streaming response so the latency lands inside an existing visible "thinking" period |
| Tool definition prompt overhead (input tokens) on every turn | Single tool, no parameters; tool description fits in ~50 tokens; negligible |
| OpenRouter sometimes mishandles `tools=[]` vs `tools=None` | The LLMClient already passes `tools=self.tools_list` unconditionally; we pass `tools` per-call from the conversation layer to keep things explicit |
| Concurrent PUT during the tool call returns inconsistent state | Tool reads fresh from disk; worst case the LLM sees the newer state, which is harmless |

## Migration Plan

None required. The change is additive and behaviour-preserving for non-edit
turns. Edit turns gain a tool-call hop; the resulting `<survey_update>` is
parsed and applied by the same code path as today.

Tests for the existing chat-turn flow continue to pass without modification
(mock LLM responses that emit no tool calls behave exactly as before).

## Open Questions

- Should the tool definition expose the `session_id` as a parameter even
  though we ignore it server-side, just for legibility in LLM trace tools?
  **Lean: no.** Adds surface area for the LLM to get wrong. The session is
  established by the request context, not by tool parameters.
- Should we add a counter metric for "edit turns with tool call" vs "edit
  turns without tool call" at structured-log level for easier grepping?
  **Lean: yes**, single counter via `logging.info` with a stable tag key.
  Cheap; pays for itself when we evaluate residual drift.
- For the soft-warning threshold ("LLM emitted `<survey_update>` without a
  prior tool call — is this concerning?"), how many such occurrences in a
  monitoring window would trigger escalation?
  **Lean: undefined at this stage.** Decide after a few days of pilot data.
