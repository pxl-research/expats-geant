"""Tool-calling helpers (core logic only).

This is adapted from the demo code in `demo_code/demos/tool_calling/`, but:
- no UI (Gradio)
- no dotenv loading
- no sys.path hacks
- no unsafe `globals()` dispatch

The goal is a small, explicit, MVP-safe tool calling loop.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    """A fully-assembled tool call emitted by the LLM stream."""

    tool_call_id: str
    name: str
    arguments_json: str

    def parse_arguments(self) -> dict[str, Any]:
        if not self.arguments_json:
            return {}
        return json.loads(self.arguments_json)


@dataclass
class CompletionResult:
    """A non-streaming completion's parsed assistant message.

    `content` is None when the model emitted only tool calls.
    `tool_calls` is an empty list when the model emitted text only.
    """

    content: str | None
    tool_calls: list[ToolCall]


ToolFn = Callable[..., Any]


class ToolCallingError(RuntimeError):
    pass


def tool_calls_from_sdk_message(message) -> list[ToolCall]:
    """Convert an OpenAI SDK chat-completion message's tool_calls to our dataclass."""
    sdk_calls = getattr(message, "tool_calls", None) or []
    return [
        ToolCall(
            tool_call_id=call.id,
            name=call.function.name,
            arguments_json=call.function.arguments or "",
        )
        for call in sdk_calls
    ]


def _collect_streamed_tool_calls(response_stream) -> tuple[str, list[ToolCall]]:
    """Collect assistant text + tool calls from a streaming response.

    Works with OpenAI-compatible `ChatCompletionChunk` streams.
    """

    assistant_text_parts: list[str] = []

    # Tool calls arrive as deltas with indices; arguments are often streamed in pieces.
    tool_calls_by_index: dict[int, dict[str, Any]] = {}

    for chunk in response_stream:
        if not getattr(chunk, "choices", None):
            continue

        delta = chunk.choices[0].delta

        # Assistant text
        content = getattr(delta, "content", None)
        if content:
            assistant_text_parts.append(content)

        # Tool calls
        delta_tool_calls = getattr(delta, "tool_calls", None)
        if not delta_tool_calls:
            continue

        for tool_call_delta in delta_tool_calls:
            idx = tool_call_delta.index
            entry = tool_calls_by_index.get(idx)
            if entry is None:
                entry = {
                    "id": tool_call_delta.id or "",
                    "name": "",
                    "arguments": "",
                }
                tool_calls_by_index[idx] = entry

            if tool_call_delta.id:
                entry["id"] = tool_call_delta.id

            fn_delta = tool_call_delta.function
            if fn_delta is None:
                continue

            if getattr(fn_delta, "name", None):
                entry["name"] = fn_delta.name

            # IMPORTANT: arguments are streamed in fragments.
            args_fragment = getattr(fn_delta, "arguments", None)
            if args_fragment:
                entry["arguments"] += args_fragment

    assistant_text = "".join(assistant_text_parts)

    tool_calls: list[ToolCall] = []
    for idx in sorted(tool_calls_by_index.keys()):
        entry = tool_calls_by_index[idx]
        tool_calls.append(
            ToolCall(
                tool_call_id=entry["id"],
                name=entry["name"],
                arguments_json=entry["arguments"],
            )
        )

    return assistant_text, tool_calls


def run_chat_with_tools(
    *,
    client,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_registry: dict[str, ToolFn],
    temperature: float = 0.0,
    extra_headers: dict[str, str] | None = None,
    max_tool_rounds: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    """Run a chat completion that may invoke tools, until no tool calls remain.

    This mirrors the demo's recursive tool-calling logic but keeps execution safe by:
    - executing only tools present in `tool_registry`
    - requiring tool args to be valid JSON

    Returns:
        (final_assistant_text, updated_messages)
    """

    for _ in range(max_tool_rounds):
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            stream=True,
            temperature=temperature,
            extra_headers=extra_headers,
        )

        assistant_text, tool_calls = _collect_streamed_tool_calls(stream)
        try:
            stream.close()
        except Exception:  # noqa: S110 - stream.close() failure is irrelevant
            pass

        # Record assistant text (if any)
        if assistant_text:
            messages.append({"role": "assistant", "content": assistant_text})

        if not tool_calls:
            return assistant_text, messages

        # Execute tool calls sequentially
        for call in tool_calls:
            if not call.name:
                raise ToolCallingError("Tool call missing function name")

            fn = tool_registry.get(call.name)
            if fn is None:
                raise ToolCallingError(f"Tool not allowed: {call.name}")

            # Add the tool-call request message
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": call.arguments_json,
                            },
                        }
                    ],
                }
            )

            try:
                args = call.parse_arguments()
            except Exception as exc:
                raise ToolCallingError(
                    f"Invalid JSON arguments for tool {call.name}: {call.arguments_json}"
                ) from exc

            result = fn(**args)

            # Add tool response
            messages.append(
                {
                    "role": "tool",
                    "name": call.name,
                    "tool_call_id": call.tool_call_id,
                    "content": json.dumps(result),
                }
            )

    raise ToolCallingError(
        f"Exceeded max_tool_rounds={max_tool_rounds} without reaching a final answer"
    )
