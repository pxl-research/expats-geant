"""Tests for m_shared/llm/tool_calling.py"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from m_shared.llm.tool_calling import (
    ToolCall,
    ToolCallingError,
    _collect_streamed_tool_calls,
    run_chat_with_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(content=None, tool_calls=None):
    """Build a minimal ChatCompletionChunk-like object."""
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


def _make_tool_call_delta(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


class _FakeStream:
    """Minimal iterable stream with a working close()."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        pass


class _BadCloseStream(_FakeStream):
    """Stream whose close() raises — used to verify errors are swallowed."""

    def close(self):
        raise RuntimeError("close failed")


# ---------------------------------------------------------------------------
# TestToolCallParseArguments
# ---------------------------------------------------------------------------


class TestToolCallParseArguments:
    def test_valid_json(self):
        call = ToolCall(tool_call_id="1", name="fn", arguments_json='{"x": 1}')
        assert call.parse_arguments() == {"x": 1}

    def test_empty_string(self):
        call = ToolCall(tool_call_id="1", name="fn", arguments_json="")
        assert call.parse_arguments() == {}

    def test_invalid_json(self):
        call = ToolCall(tool_call_id="1", name="fn", arguments_json="not-json")
        with pytest.raises(json.JSONDecodeError):
            call.parse_arguments()

    def test_nested_json(self):
        data = {"a": {"b": [1, 2, 3]}, "c": True}
        call = ToolCall(tool_call_id="1", name="fn", arguments_json=json.dumps(data))
        assert call.parse_arguments() == data


# ---------------------------------------------------------------------------
# TestCollectStreamedToolCalls
# ---------------------------------------------------------------------------


class TestCollectStreamedToolCalls:
    def test_empty_stream(self):
        text, calls = _collect_streamed_tool_calls([])
        assert text == ""
        assert calls == []

    def test_text_only(self):
        chunks = [_make_chunk(content="Hello "), _make_chunk(content="world")]
        text, calls = _collect_streamed_tool_calls(chunks)
        assert text == "Hello world"
        assert calls == []

    def test_chunk_missing_choices(self):
        # Chunk with no 'choices' attribute is skipped gracefully
        bad_chunk = SimpleNamespace()
        chunks = [bad_chunk, _make_chunk(content="ok")]
        text, calls = _collect_streamed_tool_calls(chunks)
        assert text == "ok"
        assert calls == []

    def test_single_tool_call_assembled(self):
        # Arguments arrive in two fragments
        tc1 = _make_tool_call_delta(index=0, id="tc1", name="my_tool", arguments=None)
        tc2 = _make_tool_call_delta(index=0, id=None, name=None, arguments='{"x":')
        tc3 = _make_tool_call_delta(index=0, id=None, name=None, arguments='"val"}')
        chunks = [
            _make_chunk(tool_calls=[tc1]),
            _make_chunk(tool_calls=[tc2]),
            _make_chunk(tool_calls=[tc3]),
        ]
        text, calls = _collect_streamed_tool_calls(chunks)
        assert text == ""
        assert len(calls) == 1
        assert calls[0].tool_call_id == "tc1"
        assert calls[0].name == "my_tool"
        assert calls[0].arguments_json == '{"x":"val"}'

    def test_multiple_tool_calls(self):
        tc_a = _make_tool_call_delta(index=0, id="a", name="tool_a", arguments='{"a":1}')
        tc_b = _make_tool_call_delta(index=1, id="b", name="tool_b", arguments='{"b":2}')
        chunks = [_make_chunk(tool_calls=[tc_a]), _make_chunk(tool_calls=[tc_b])]
        text, calls = _collect_streamed_tool_calls(chunks)
        assert len(calls) == 2
        assert calls[0].name == "tool_a"
        assert calls[1].name == "tool_b"

    def test_function_none_skipped(self):
        # fn_delta is None → entry is created (id set) but function details are skipped
        tc = SimpleNamespace(index=0, id="x", function=None)
        chunk = _make_chunk(tool_calls=[tc])
        text, calls = _collect_streamed_tool_calls([chunk])
        # Entry exists but name is empty (no function info processed)
        assert len(calls) == 1
        assert calls[0].name == ""

    def test_mixed_text_and_tool_call(self):
        tc = _make_tool_call_delta(index=0, id="tc", name="fn", arguments="{}")
        chunks = [
            _make_chunk(content="thinking..."),
            _make_chunk(tool_calls=[tc]),
            _make_chunk(content="done"),
        ]
        text, calls = _collect_streamed_tool_calls(chunks)
        assert "thinking" in text
        assert "done" in text
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# TestRunChatWithTools
# ---------------------------------------------------------------------------


class TestRunChatWithTools:
    """Tests for run_chat_with_tools() — the main tool-calling loop."""

    def _client(self, *streams):
        """Build a mock OpenAI client that returns given streams in order."""
        mock = MagicMock()
        if len(streams) == 1:
            mock.chat.completions.create.return_value = streams[0]
        else:
            mock.chat.completions.create.side_effect = list(streams)
        return mock

    def test_no_tool_calls_returns_immediately(self):
        stream = _FakeStream([_make_chunk(content="Hello")])
        client = self._client(stream)
        text, messages = run_chat_with_tools(
            client=client,
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            tool_registry={},
        )
        assert text == "Hello"
        assert client.chat.completions.create.call_count == 1

    def test_single_tool_call_executed(self):
        tc = _make_tool_call_delta(index=0, id="c1", name="add", arguments='{"a":1,"b":2}')
        first = _FakeStream([_make_chunk(tool_calls=[tc])])
        second = _FakeStream([_make_chunk(content="Result: 3")])
        client = self._client(first, second)

        add_fn = MagicMock(return_value=3)
        text, _ = run_chat_with_tools(
            client=client,
            model="gpt-4",
            messages=[{"role": "user", "content": "add 1 and 2"}],
            tools=[],
            tool_registry={"add": add_fn},
        )
        add_fn.assert_called_once_with(a=1, b=2)
        assert text == "Result: 3"

    def test_tool_missing_name_raises(self):
        # fn_delta.name is None → name stays "" → ToolCallingError
        tc = SimpleNamespace(index=0, id="c1", function=SimpleNamespace(name=None, arguments=None))
        stream = _FakeStream([_make_chunk(tool_calls=[tc])])
        client = self._client(stream)
        with pytest.raises(ToolCallingError, match="missing function name"):
            run_chat_with_tools(
                client=client,
                model="gpt-4",
                messages=[],
                tools=[],
                tool_registry={},
            )

    def test_unknown_tool_raises(self):
        tc = _make_tool_call_delta(index=0, id="c1", name="unknown_fn", arguments="{}")
        stream = _FakeStream([_make_chunk(tool_calls=[tc])])
        client = self._client(stream)
        with pytest.raises(ToolCallingError, match="Tool not allowed: unknown_fn"):
            run_chat_with_tools(
                client=client,
                model="gpt-4",
                messages=[],
                tools=[],
                tool_registry={},
            )

    def test_invalid_json_args_raises(self):
        tc = _make_tool_call_delta(index=0, id="c1", name="my_tool", arguments="not-json")
        stream = _FakeStream([_make_chunk(tool_calls=[tc])])
        client = self._client(stream)
        with pytest.raises(ToolCallingError, match="Invalid JSON arguments"):
            run_chat_with_tools(
                client=client,
                model="gpt-4",
                messages=[],
                tools=[],
                tool_registry={"my_tool": MagicMock()},
            )

    def test_stream_close_failure_ignored(self):
        stream = _BadCloseStream([_make_chunk(content="text")])
        client = self._client(stream)
        # Should not raise even though close() fails
        text, _ = run_chat_with_tools(
            client=client,
            model="gpt-4",
            messages=[],
            tools=[],
            tool_registry={},
        )
        assert text == "text"

    def test_exceeds_max_rounds_raises(self):
        def _make_tool_stream():
            tc = _make_tool_call_delta(index=0, id="c", name="noop", arguments="{}")
            return _FakeStream([_make_chunk(tool_calls=[tc])])

        mock = MagicMock()
        mock.chat.completions.create.side_effect = lambda **kwargs: _make_tool_stream()

        with pytest.raises(ToolCallingError, match="Exceeded max_tool_rounds=3"):
            run_chat_with_tools(
                client=mock,
                model="gpt-4",
                messages=[],
                tools=[],
                tool_registry={"noop": lambda: "ok"},
                max_tool_rounds=3,
            )

    def test_assistant_text_appended_to_messages(self):
        tc = _make_tool_call_delta(index=0, id="c1", name="fn", arguments="{}")
        first = _FakeStream([_make_chunk(content="thinking..."), _make_chunk(tool_calls=[tc])])
        second = _FakeStream([_make_chunk(content="done")])
        client = self._client(first, second)

        _, messages = run_chat_with_tools(
            client=client,
            model="gpt-4",
            messages=[{"role": "user", "content": "go"}],
            tools=[],
            tool_registry={"fn": lambda: "result"},
        )
        # The assistant text from the first round should be present
        text_msgs = [
            m
            for m in messages
            if m.get("role") == "assistant" and m.get("content") == "thinking..."
        ]
        assert len(text_msgs) == 1

    def test_extra_headers_forwarded(self):
        stream = _FakeStream([_make_chunk(content="ok")])
        mock = MagicMock()
        mock.chat.completions.create.return_value = stream

        run_chat_with_tools(
            client=mock,
            model="gpt-4",
            messages=[],
            tools=[],
            tool_registry={},
            extra_headers={"X-Custom": "header"},
        )
        call_kwargs = mock.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_headers"] == {"X-Custom": "header"}
