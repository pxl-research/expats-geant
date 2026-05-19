## ADDED Requirements

### Requirement: Tool Call Return Access

The LLM client SHALL expose a completion method that returns the full response
message — both textual content and any tool calls — so that callers
implementing a tool-call loop can dispatch tool invocations and continue the
conversation. The existing content-only completion method SHALL remain
available for backwards compatibility with callers that do not use tools.

The method SHALL accept a `tools` parameter per call so that different
endpoints can advertise different tool surfaces against a shared `LLMClient`
instance without mutating the client's default `tools_list`.

The retry, backoff, headers, temperature, and extended-thinking behaviours
that apply to the content-only completion SHALL also apply to the new method.

#### Scenario: Text-only response returned

- **WHEN** the new method is called and the model returns a message with
  content and no tool calls
- **THEN** the method SHALL return a result whose content is the model text
- **AND** whose tool-call list is empty

#### Scenario: Tool call surfaced to the caller

- **WHEN** the new method is called and the model returns a message containing
  a tool call
- **THEN** the method SHALL return a result whose tool-call list contains the
  call's name, arguments, and call identifier
- **AND** the caller SHALL be able to dispatch the call and append a tool
  result message before the next iteration

#### Scenario: Per-call tools override

- **WHEN** the new method is called with an explicit `tools` argument
- **THEN** that tool list SHALL be sent to the model for that call only
- **AND** the client's default `tools_list` SHALL NOT be mutated
