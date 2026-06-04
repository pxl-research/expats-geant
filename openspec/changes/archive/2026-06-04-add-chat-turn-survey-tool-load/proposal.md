# Proposal: Chat-turn survey draft loaded via LLM tool call

## Why

A pilot integrator reported that PUTting an edited survey to
`/chat/{session_id}/survey` and then sending any chat message silently
overwrites the user's edits. We reproduced the clobber end-to-end. The root
cause is **not** stale state on the server: the chat turn loads the draft fresh
from disk on every call (`shape_api/conversation.py:104`). The cause is that
the draft is then projected through `compact_survey_summary`
(`shape_api/suggestion_engine.py:21-28`) before being given to the LLM. That
summary contains only the survey title, section titles, and question text — no
IDs, no question types, no `answer_options`, no required flags, no min/max, no
metadata.

The system prompt then asks the LLM to "Output the COMPLETE survey JSON"
inside `<survey_update>` tags (`conversation.py:89`). The parser at
`conversation.py:128-149` accepts any well-formed Survey JSON and **overwrites**
the on-disk draft via `save_draft_survey`. So whenever the LLM emits an update,
it has to confabulate every field the summary did not contain — and that
confabulation is what wipes the user's PUT edits.

This proposal is the smallest viable step that fixes the practical clobber
**and** establishes the LLM tool-calling infrastructure as a foundation. We
deliberately stop short of the bigger redesign (multi-tool patch contract); we
will revisit that if pilot feedback shows residual drift remains painful after
this change ships.

## What Changes

- `compact_survey_summary` is enriched to anchor each section and question with
  its **ID** — and nothing else. Format: `[sec_id] Section title` and
  `[q_id] Question text`. Types, options, metadata, etc. remain deliberately
  absent from the summary; that is precisely what the tool is for.
- A single LLM tool `get_full_survey` is introduced. When called, it returns the
  full JSON of the current draft for the session, read from disk at call time.
  No parameters: the session is implicit in the chat-turn context.
- `m_shared/llm/client.py` gains a new method that returns the full response
  message (content **and** tool_calls). The existing `create_completion(...)`
  method, which only returns `.content`, remains untouched for backwards
  compatibility with non-tool callers.
- `execute_chat_turn` implements a small tool-call loop. On each iteration:
  call the LLM with the conversation messages and the `[get_full_survey]` tool
  definition; if the response contains tool calls, dispatch each one, append the
  call **and** result to the messages array, and loop. If the response contains
  no tool calls, exit the loop and continue with the existing `<survey_update>`
  handling. The loop is capped at a small number of iterations.
- The system prompt is updated to tell the LLM that the summary intentionally
  omits fields and that it MUST call `get_full_survey` before emitting a
  `<survey_update>`. The instruction is a **soft** prompt directive; it is
  **not** enforced server-side. When the LLM emits `<survey_update>` without
  having called the tool, the server still applies it, but a warning is logged
  so we can monitor compliance.
- Each `get_full_survey` invocation produces a structured log line tagged with
  the session ID and an in-turn iteration counter, so we can answer "did the
  LLM actually load the draft on this turn?" from logs.

## Impact

- **Affected specs:**
  - `questionnaire-design`: MODIFIED `Conversational Session API` (the chat turn
    now runs a tool-call loop and uses an ID-anchored summary). ADDED
    `Chat Turn Tool Surface` (the tool semantics, loop cap, soft instruction,
    logging).
  - `llm-integration`: ADDED `Tool Call Return Access` (the new method that
    exposes both content and tool calls from a completion).
- **Affected code:**
  - `m_shared/llm/client.py` — new method for full-message return.
  - `shape_api/conversation.py` — prompt rewrite, tool-call loop.
  - `shape_api/suggestion_engine.py` — ID-anchored summary.
  - `shape_api/tools.py` (new file) — `get_full_survey` tool definition and
    dispatcher.
- **Behaviour change for clients:** none observable from the HTTP API contract.
  Internal: one extra LLM round-trip per chat turn where the model elects to
  call the tool (i.e. typically only edit turns). Pure Q&A turns remain
  single-round-trip.
- **Latency:** ~1 second additional perceived latency on Gemini-flash-class
  models for turns that load the draft. Acceptable trade-off for correctness.
- **No data-shape changes.** No client-visible API contract changes. No new
  endpoints. No database changes.
