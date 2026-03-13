"""Tests for m_chat.tagging_engine."""

from unittest.mock import Mock

import pytest

from m_chat.session import update_vocabulary
from m_chat.tagging_engine import normalise_tag, suggest_tags
from m_shared.llm.client import LLMClient
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_q(qid: str = "q1", text: str = "Describe your experience.") -> Question:
    return Question(id=qid, text=text, type=QuestionType.OPEN_ENDED)


def _choice_q(qid: str = "q1") -> Question:
    return Question(
        id=qid,
        text="How satisfied are you?",
        type=QuestionType.SINGLE_CHOICE,
        answer_options=[AnswerOption(id=f"opt{i}", text=f"Option {i}") for i in range(4)],
    )


@pytest.fixture
def mock_llm():
    client = Mock(spec=LLMClient)
    client.create_completion.return_value = '["tag-one", "tag-two"]'
    return client


# ---------------------------------------------------------------------------
# normalise_tag
# ---------------------------------------------------------------------------


def test_normalise_tag_lowercase():
    assert normalise_tag("Demographics") == "demographics"


def test_normalise_tag_strip_whitespace():
    assert normalise_tag("  tag  ") == "tag"


def test_normalise_tag_spaces_to_dashes():
    assert normalise_tag("work life balance") == "work-life-balance"


def test_normalise_tag_already_normalised():
    assert normalise_tag("already-normalised") == "already-normalised"


def test_normalise_tag_mixed():
    assert normalise_tag("  Work Life ") == "work-life"


# ---------------------------------------------------------------------------
# suggest_tags — without vocabulary
# ---------------------------------------------------------------------------


def test_suggest_tags_returns_list(mock_llm):
    q = _open_q()
    result = suggest_tags(q, mock_llm)
    assert isinstance(result, list)


def test_suggest_tags_normalised(mock_llm):
    mock_llm.create_completion.return_value = '["Demographics", "Work Life"]'
    q = _open_q()
    result = suggest_tags(q, mock_llm)
    assert "demographics" in result
    assert "work-life" in result


def test_suggest_tags_without_vocabulary_prompt_no_existing_tags(mock_llm):
    q = _open_q()
    suggest_tags(q, mock_llm, vocabulary=None)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt = messages[0]["content"]
    assert "Existing tags" not in prompt


def test_suggest_tags_question_text_in_prompt(mock_llm):
    q = _open_q(text="What is your job role?")
    suggest_tags(q, mock_llm)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt = messages[1]["content"]
    assert "What is your job role?" in prompt


# ---------------------------------------------------------------------------
# suggest_tags — with vocabulary
# ---------------------------------------------------------------------------


def test_suggest_tags_with_vocabulary_in_prompt(mock_llm):
    q = _open_q()
    vocab = {"age": ["q0"], "gender": ["q0"]}
    suggest_tags(q, mock_llm, vocabulary=vocab)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt = messages[0]["content"]
    assert "age" in prompt or "gender" in prompt
    assert "Existing tags" in prompt


def test_suggest_tags_with_empty_vocabulary_behaves_like_none(mock_llm):
    q = _open_q()
    result_no_vocab = suggest_tags(q, mock_llm, vocabulary=None)
    result_empty_vocab = suggest_tags(q, mock_llm, vocabulary={})
    # Both should produce tags; no crash
    assert isinstance(result_no_vocab, list)
    assert isinstance(result_empty_vocab, list)


# ---------------------------------------------------------------------------
# suggest_tags — language from style profile
# ---------------------------------------------------------------------------


def test_suggest_tags_language_in_prompt(mock_llm):
    q = _open_q()
    profile = {"language": "nl"}
    suggest_tags(q, mock_llm, style_profile=profile)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt = messages[0]["content"]
    assert "Dutch" in prompt


# ---------------------------------------------------------------------------
# JSON parse edge cases
# ---------------------------------------------------------------------------


def test_suggest_tags_strips_markdown_fences():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = '```json\n["tag-a", "tag-b"]\n```'
    q = _open_q()
    result = suggest_tags(q, mock_llm)
    assert "tag-a" in result
    assert "tag-b" in result


def test_suggest_tags_invalid_json_returns_empty():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "not json at all"
    q = _open_q()
    result = suggest_tags(q, mock_llm)
    assert result == []


def test_suggest_tags_non_array_json_returns_empty():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = '{"tag": "value"}'
    q = _open_q()
    result = suggest_tags(q, mock_llm)
    assert result == []


# ---------------------------------------------------------------------------
# update_vocabulary integration
# ---------------------------------------------------------------------------


def test_update_vocabulary_with_suggested_tags():
    vocab = {}
    tags = ["demographics", "age group"]
    result = update_vocabulary(vocab, tags, "q1")
    assert "demographics" in result
    assert "age-group" in result
    assert "q1" in result["demographics"]


def test_update_vocabulary_accumulates_across_questions():
    vocab = {}
    vocab = update_vocabulary(vocab, ["demographics"], "q1")
    vocab = update_vocabulary(vocab, ["demographics", "gender"], "q2")
    assert "q1" in vocab["demographics"]
    assert "q2" in vocab["demographics"]
    assert "q2" in vocab["gender"]
