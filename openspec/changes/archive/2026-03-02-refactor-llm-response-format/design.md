# Design: LLM Response Format — JSON vs Plain Text

## Context

The RAG pipeline instructs the LLM to return structured data (answer text, an optional choice selection, optional reasoning) in a single completion call. The format used to encode this structure determines how reliably the data can be extracted.

## Goals / Non-Goals

- **Goals:** Reliable multi-line answer extraction; consistent format across single and batch endpoints; detectable parse failures; machine-processable `selected` field
- **Non-Goals:** Streaming responses; function calling / tool use for answer generation; schema validation beyond basic field extraction

## Decisions

### Use JSON as the response format

**Decision:** Instruct the LLM to respond with a JSON object.

**Format:**
```json
{
  "answer": "...",
  "selected": "c1",
  "reasoning": "..."
}
```

`selected` is a string (single choice), a list of strings (multiple choice), or `null`. `reasoning` is a string or `null`.

**Alternatives considered:**

| Format | Verdict |
|---|---|
| Plain-text prefixes (`ANSWER:`, `REASONING:`) | Current approach. Fragile, no multi-line support without custom block parser. Rejected. |
| Markdown headers (`## Answer\n...`) | Human-readable, multi-line friendly, but still requires custom parsing. Not meaningfully better than JSON for machine use. Rejected. |
| JSON | Unambiguous, multi-line native, standard `json.loads()`. Parse errors are detectable. **Selected.** |
| OpenAI structured outputs / response_schema | Guarantees valid JSON at the API level. Not universally supported across OpenRouter models. Deferred to future phase. |

### Fallback on JSON parse failure

**Decision:** If `json.loads()` fails, treat the full raw response as `answer` and set `selected` and `reasoning` to `null`. Log the parse failure.

**Rationale:** Silent degradation is preferable to a 500 error for the user. The answer field is the most important output; citations are derived from retrieval (not the LLM response), so they are unaffected.

### Strip markdown code fences

**Decision:** Before parsing, strip ` ```json ... ``` ` and ` ``` ... ``` ` wrappers.

**Rationale:** Several common models (including instruction-tuned variants) wrap JSON in markdown fences even when instructed not to. Stripping is a single regex and prevents unnecessary fallback.

### Align single and batch prompt formats

**Decision:** `suggest_answer()` (single endpoint) adopts the same JSON prompt as `suggest_batch()`.

**Rationale:** Two different prompt formats for the same underlying task creates maintenance burden and inconsistent LLM behaviour. `selected` is simply omitted from the prompt for `open_ended` questions (same as current batch behaviour).

## Risks / Trade-offs

- **JSON reliability:** Most modern LLMs handle JSON output well, but smaller/cheaper models may struggle. Mitigated by the fallback strategy and code-fence stripping.
- **Token overhead:** JSON field names add ~20 tokens per response. Negligible at current scale.
- **Temperature:** No change needed — JSON output is not significantly affected by temperature in the 0.3–0.5 range used here.

## Open Questions

- Should we adopt OpenAI structured outputs (response_schema) for models that support it? Deferred — adds model-specific branching logic, better suited for a future optimisation pass.
