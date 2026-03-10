"""Tests for m_chat.suggestion_engine."""

import json
from unittest.mock import Mock

import pytest

from m_chat.suggestion_engine import SuggestionResult, _compact_survey_summary, suggest_question
from m_shared.llm.client import LLMClient
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_question(
    q_id: str = "q1",
    text: str = "How satisfied are you?",
    q_type: QuestionType = QuestionType.SINGLE_CHOICE,
    options: list[str] | None = None,
) -> Question:
    if options is None:
        options = ["Very satisfied", "Satisfied", "Neutral", "Dissatisfied"]
    return Question(
        id=q_id,
        text=text,
        type=q_type,
        answer_options=[AnswerOption(id=f"opt{i}", text=o) for i, o in enumerate(options)],
    )


def _make_survey() -> Survey:
    return Survey(
        id="s1",
        title="Employee Survey",
        sections=[
            Section(
                id="sec1",
                title="Wellbeing",
                questions=[
                    _make_question("q1", "How happy are you at work?"),
                    _make_question("q2", "Would you recommend us to others?"),
                ],
            )
        ],
    )


def _valid_llm_response(n: int = 3) -> str:
    return json.dumps([{"phrasing": f"Phrasing {i}", "reasoning": f"Reason {i}"} for i in range(n)])


@pytest.fixture
def mock_llm():
    client = Mock(spec=LLMClient)
    client.create_completion.return_value = _valid_llm_response(3)
    return client


# ---------------------------------------------------------------------------
# _compact_survey_summary
# ---------------------------------------------------------------------------


def test_compact_survey_summary_includes_title():
    survey = _make_survey()
    result = _compact_survey_summary(survey)
    assert "Employee Survey" in result


def test_compact_survey_summary_includes_section():
    survey = _make_survey()
    result = _compact_survey_summary(survey)
    assert "Wellbeing" in result


def test_compact_survey_summary_includes_question_texts():
    survey = _make_survey()
    result = _compact_survey_summary(survey)
    assert "How happy are you at work?" in result


def test_compact_survey_summary_no_metadata():
    survey = _make_survey()
    result = _compact_survey_summary(survey)
    # Should not contain raw metadata field names
    assert "metadata" not in result


# ---------------------------------------------------------------------------
# suggest_question — without context
# ---------------------------------------------------------------------------


def test_suggest_question_returns_list(mock_llm):
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert isinstance(results, list)


def test_suggest_question_returns_suggestion_results(mock_llm):
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert all(isinstance(r, SuggestionResult) for r in results)


def test_suggest_question_default_n_suggestions(mock_llm):
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert len(results) == 3


def test_suggest_question_phrasing_not_empty(mock_llm):
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert all(r.phrasing for r in results)


# ---------------------------------------------------------------------------
# suggest_question — with survey context
# ---------------------------------------------------------------------------


def test_suggest_question_with_survey_includes_summary_in_prompt(mock_llm):
    q = _make_question()
    survey = _make_survey()
    suggest_question(q, mock_llm, survey_context=survey)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    assert "Employee Survey" in user_msg


def test_suggest_question_without_survey_context(mock_llm):
    q = _make_question()
    results = suggest_question(q, mock_llm, survey_context=None)
    assert len(results) > 0


# ---------------------------------------------------------------------------
# suggest_question — with style profile
# ---------------------------------------------------------------------------


def test_suggest_question_with_style_profile_in_system_message(mock_llm):
    q = _make_question()
    profile = {
        "language": "nl",
        "free_text": "Formeel taalgebruik.",
        "document_summary": "",
        "defaults_applied": False,
    }
    suggest_question(q, mock_llm, style_profile=profile)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    assert "Dutch" in system_msg or "nl" in system_msg


# ---------------------------------------------------------------------------
# JSON parse fallback
# ---------------------------------------------------------------------------


def test_suggest_question_fallback_on_invalid_json():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "not valid json at all"
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert len(results) == 1
    assert results[0].phrasing == "not valid json at all"


def test_suggest_question_fallback_on_non_array_json():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = '{"phrasing": "single", "reasoning": "r"}'
    q = _make_question()
    results = suggest_question(q, mock_llm)
    # Non-array JSON falls back to raw text
    assert len(results) == 1


def test_suggest_question_strips_markdown_fences():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = (
        "```json\n" '[{"phrasing": "Clean phrasing", "reasoning": "Good"}]\n' "```"
    )
    q = _make_question()
    results = suggest_question(q, mock_llm)
    assert len(results) == 1
    assert results[0].phrasing == "Clean phrasing"


# ---------------------------------------------------------------------------
# n_suggestions parameter
# ---------------------------------------------------------------------------


def test_suggest_question_n_suggestions_in_prompt(mock_llm):
    q = _make_question()
    suggest_question(q, mock_llm, n_suggestions=5)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    assert "5" in user_msg


def test_suggest_question_question_type_in_prompt(mock_llm):
    q2 = Question(id="q_open", text="Describe your experience.", type=QuestionType.OPEN_ENDED)
    suggest_question(q2, mock_llm)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    assert "open_ended" in user_msg
