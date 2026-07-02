"""Tests for m_shared.utils.llm_parsing."""

import json

from m_shared.utils.llm_parsing import extract_json_object, strip_code_fences


def test_extract_json_object_plain():
    text = '{"answer": "Man", "reasoning": null}'
    assert json.loads(extract_json_object(text)) == {"answer": "Man", "reasoning": None}


def test_extract_json_object_with_surrounding_prose():
    text = 'Sure, here is the answer:\n{"answer": "Man"}\nHope that helps!'
    assert json.loads(extract_json_object(text)) == {"answer": "Man"}


def test_extract_json_object_fenced():
    text = '```json\n{"answer": "Man"}\n```'
    assert json.loads(extract_json_object(text)) == {"answer": "Man"}


def test_extract_json_object_fenced_no_language_tag():
    text = '```\n{"answer": "Man"}\n```'
    assert json.loads(extract_json_object(text)) == {"answer": "Man"}


def test_extract_json_object_ignores_braces_inside_strings():
    text = '{"answer": "uses {curly} braces in text", "reasoning": null}'
    parsed = json.loads(extract_json_object(text))
    assert parsed["answer"] == "uses {curly} braces in text"


def test_extract_json_object_self_correction_takes_last_block():
    """Regression: model emits a draft answer, reconsiders in prose, then
    restates a final answer as a second JSON object. The greedy first-to-last
    brace regex used to swallow both objects plus the prose between them,
    producing invalid JSON and leaking the raw completion as the answer.
    """
    text = (
        '{\n  "answer": "Laravel",\n  "reasoning": "first guess"\n}\n\n'
        "Wait, let me reconsider. Laravel is already covered by the listed choice.\n\n"
        '{\n  "answer": null,\n  "reasoning": "already covered by an existing choice"\n}'
    )
    parsed = json.loads(extract_json_object(text))
    assert parsed == {"answer": None, "reasoning": "already covered by an existing choice"}


def test_extract_json_object_no_object_returns_original_text():
    text = "No relevant information found."
    assert extract_json_object(text) == text


def test_strip_code_fences_unfenced_passthrough():
    assert strip_code_fences("  plain text  ") == "plain text"
