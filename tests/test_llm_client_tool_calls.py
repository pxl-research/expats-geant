"""Unit tests for LLMClient.create_completion_full (tool-call-aware completion)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from m_shared.llm import LLMClient
from m_shared.llm.tool_calling import CompletionResult, ToolCall


def _sdk_message(content=None, tool_calls=None):
    """Build a fake OpenAI SDK message object."""
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _sdk_response(content=None, tool_calls=None):
    """Build a fake OpenAI SDK completion response."""
    return SimpleNamespace(choices=[SimpleNamespace(message=_sdk_message(content, tool_calls))])


def _sdk_tool_call(call_id, name, arguments):
    """Build a fake OpenAI SDK tool-call delta as it appears on a complete message."""
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class TestCreateCompletionFull:
    def test_text_only_response(self):
        client = LLMClient(api_key="test-key")
        client._retry_with_backoff = MagicMock(return_value=_sdk_response(content="hi"))

        result = client.create_completion_full(messages=[{"role": "user", "content": "hello"}])

        assert isinstance(result, CompletionResult)
        assert result.content == "hi"
        assert result.tool_calls == []

    def test_single_tool_call_surfaced(self):
        client = LLMClient(api_key="test-key")
        sdk_call = _sdk_tool_call("call_1", "get_full_survey", "{}")
        client._retry_with_backoff = MagicMock(
            return_value=_sdk_response(content=None, tool_calls=[sdk_call])
        )

        result = client.create_completion_full(messages=[{"role": "user", "content": "edit"}])

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0] == ToolCall(
            tool_call_id="call_1", name="get_full_survey", arguments_json="{}"
        )

    def test_multiple_tool_calls_in_one_message(self):
        client = LLMClient(api_key="test-key")
        sdk_calls = [
            _sdk_tool_call("a", "tool_a", '{"x": 1}'),
            _sdk_tool_call("b", "tool_b", '{"y": 2}'),
        ]
        client._retry_with_backoff = MagicMock(
            return_value=_sdk_response(content=None, tool_calls=sdk_calls)
        )

        result = client.create_completion_full(messages=[{"role": "user", "content": "do both"}])

        assert [tc.name for tc in result.tool_calls] == ["tool_a", "tool_b"]
        assert [tc.tool_call_id for tc in result.tool_calls] == ["a", "b"]

    def test_per_call_tools_argument_passed_through(self):
        client = LLMClient(api_key="test-key", tools_list=[{"default_tool": True}])
        client._retry_with_backoff = MagicMock(return_value=_sdk_response(content="ok"))

        per_call_tools = [{"function": {"name": "x"}}]
        client.create_completion_full(messages=[], tools=per_call_tools)

        kwargs = client._retry_with_backoff.call_args.kwargs
        assert kwargs["tools"] == per_call_tools

    def test_per_call_tools_none_falls_back_to_client_default(self):
        default_tools = [{"default_tool": True}]
        client = LLMClient(api_key="test-key", tools_list=default_tools)
        client._retry_with_backoff = MagicMock(return_value=_sdk_response(content="ok"))

        client.create_completion_full(messages=[])

        kwargs = client._retry_with_backoff.call_args.kwargs
        assert kwargs["tools"] == default_tools

    def test_temperature_override_per_call(self):
        client = LLMClient(api_key="test-key", temperature=0.7)
        client._retry_with_backoff = MagicMock(return_value=_sdk_response(content="ok"))

        client.create_completion_full(messages=[], temperature=0.0)

        kwargs = client._retry_with_backoff.call_args.kwargs
        assert kwargs["temperature"] == 0.0

    def test_arguments_default_to_empty_string_when_none(self):
        """OpenAI SDK can return `function.arguments=None` for parameterless calls."""
        client = LLMClient(api_key="test-key")
        sdk_call = _sdk_tool_call("call_1", "get_full_survey", None)
        client._retry_with_backoff = MagicMock(
            return_value=_sdk_response(content=None, tool_calls=[sdk_call])
        )

        result = client.create_completion_full(messages=[])

        assert result.tool_calls[0].arguments_json == ""
