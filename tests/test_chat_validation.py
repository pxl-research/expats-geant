"""Tests for m_chat.validation_engine."""

import json
from unittest.mock import Mock

from m_chat.validation_engine import (
    ValidationIssue,
    _check_survey_tier1,
    validate_question,
    validate_survey,
)
from m_shared.llm.client import LLMClient
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt(i: int, text: str = "") -> AnswerOption:
    return AnswerOption(id=f"opt{i}", text=text or f"Option {i}")


def _choice_q(
    qid: str = "q1",
    text: str = "How satisfied are you?",
    n_opts: int = 5,
    q_type: QuestionType = QuestionType.SINGLE_CHOICE,
    opt_texts: list[str] | None = None,
) -> Question:
    if opt_texts is not None:
        opts = [AnswerOption(id=f"opt{i}", text=t) for i, t in enumerate(opt_texts)]
    else:
        opts = [_opt(i) for i in range(n_opts)]
    return Question(id=qid, text=text, type=q_type, answer_options=opts)


def _open_q(qid: str = "q1", text: str = "Describe your experience.") -> Question:
    return Question(id=qid, text=text, type=QuestionType.OPEN_ENDED)


def _slider_q(
    qid: str = "q1", text: str = "Rate from 0–10.", labels: dict | None = None
) -> Question:
    meta = {}
    if labels:
        meta["labels"] = labels
    return Question(
        id=qid,
        text=text,
        type=QuestionType.SLIDER,
        min_value=0,
        max_value=10,
        metadata=meta,
    )


def _make_survey(questions: list[Question]) -> Survey:
    return Survey(
        id="s1",
        title="Survey",
        sections=[Section(id="sec1", title="Section", questions=questions)],
    )


# ---------------------------------------------------------------------------
# Tier 1: double_barreled
# ---------------------------------------------------------------------------


def test_double_barreled_detected():
    q = _open_q(text="Do you like and enjoy working here?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "double_barreled" in codes


def test_double_barreled_not_flagged_simple():
    q = _open_q(text="How satisfied are you with your role?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "double_barreled" not in codes


def test_double_barreled_or_conjunction():
    q = _open_q(text="Do you use or prefer remote working?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "double_barreled" in codes


# ---------------------------------------------------------------------------
# Tier 1: scale_too_short / scale_too_long
# ---------------------------------------------------------------------------


def test_scale_too_short_3_options():
    q = _choice_q(n_opts=3)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_short" in codes


def test_scale_too_short_1_option():
    q = _choice_q(n_opts=1)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_short" in codes


def test_scale_exactly_4_options_no_short_warning():
    q = _choice_q(n_opts=4)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_short" not in codes


def test_scale_too_long_8_options():
    q = _choice_q(n_opts=8)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_long" in codes


def test_scale_exactly_7_options_no_long_warning():
    q = _choice_q(n_opts=7)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_long" not in codes


def test_scale_5_options_no_length_warnings():
    q = _choice_q(n_opts=5)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_short" not in codes
    assert "scale_too_long" not in codes


def test_scale_multiple_choice_also_checked():
    q = _choice_q(n_opts=2, q_type=QuestionType.MULTIPLE_CHOICE)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "scale_too_short" in codes


# ---------------------------------------------------------------------------
# Tier 1: slider_no_labels
# ---------------------------------------------------------------------------


def test_slider_no_labels_flagged():
    q = _slider_q()
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "slider_no_labels" in codes


def test_slider_with_labels_not_flagged():
    q = _slider_q(labels={"min": "Never", "max": "Always"})
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "slider_no_labels" not in codes


# ---------------------------------------------------------------------------
# Tier 1: leading_language
# ---------------------------------------------------------------------------


def test_leading_language_obviously():
    q = _open_q(text="Obviously, you would prefer option A, right?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "leading_language" in codes


def test_leading_language_surely():
    q = _open_q(text="Surely you agree with our approach?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "leading_language" in codes


def test_leading_language_dont_you_think():
    q = _open_q(text="Don't you think remote work is better?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "leading_language" in codes


def test_leading_language_of_course():
    q = _open_q(text="Of course you prefer a higher salary?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "leading_language" in codes


def test_no_leading_language_neutral():
    q = _open_q(text="How do you feel about remote work?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "leading_language" not in codes


# ---------------------------------------------------------------------------
# Tier 1: likert_unlabelled
# ---------------------------------------------------------------------------


def test_likert_unlabelled_detected():
    q = _choice_q(n_opts=5, opt_texts=["Agree", "", "Neutral", "", "Disagree"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "likert_unlabelled" in codes


def test_likert_all_labelled_not_flagged():
    q = _choice_q(n_opts=5)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "likert_unlabelled" not in codes


def test_likert_unlabelled_not_triggered_for_3_options():
    # < 4 options: scale_too_short fires but NOT likert_unlabelled
    q = _choice_q(n_opts=3, opt_texts=["Yes", "", "No"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "likert_unlabelled" not in codes


# ---------------------------------------------------------------------------
# validate_question without LLM — tier1 only
# ---------------------------------------------------------------------------


def test_validate_question_no_llm_no_tier2():
    q = _open_q(text="Describe your role.")
    issues = validate_question(q, llm_client=None)
    # Tier 1 only; no issues expected for a clean question
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# validate_question with LLM — tier2 fires
# ---------------------------------------------------------------------------


def test_validate_question_with_llm_calls_client():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "[]"
    q = _open_q()
    validate_question(q, llm_client=mock_llm)
    mock_llm.create_completion.assert_called_once()


def test_validate_question_llm_issues_returned():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = json.dumps(
        [{"code": "ambiguous", "severity": "warning", "message": "Too vague."}]
    )
    q = _open_q()
    issues = validate_question(q, llm_client=mock_llm)
    codes = [i.code for i in issues]
    assert "ambiguous" in codes


def test_validate_question_llm_prompt_contains_question_text():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "[]"
    q = _open_q(text="What is your work experience level?")
    validate_question(q, llm_client=mock_llm)

    call_args = mock_llm.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    full_text = " ".join(m["content"] for m in messages)
    assert "What is your work experience level?" in full_text


def test_validate_question_llm_malformed_response_ignored():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "definitely not json"
    q = _open_q()
    issues = validate_question(q, llm_client=mock_llm)
    # No crash, LLM issues silently dropped
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# validate_survey
# ---------------------------------------------------------------------------


def test_validate_survey_all_questions_covered():
    questions = [
        _choice_q("q1", n_opts=3),  # scale_too_short
        _open_q("q2", text="Obviously, do you agree?"),  # leading_language
        _slider_q("q3"),  # slider_no_labels
    ]
    survey = _make_survey(questions)
    issues = validate_survey(survey)
    ids = [i.question_id for i in issues]
    assert "q1" in ids
    assert "q2" in ids
    assert "q3" in ids


def test_validate_survey_no_llm_tier1_only():
    survey = _make_survey([_open_q("q1")])
    issues = validate_survey(survey, llm_client=None)
    assert isinstance(issues, list)


def test_validate_survey_with_llm_calls_batch():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = "[]"
    survey = _make_survey([_open_q("q1"), _open_q("q2")])
    validate_survey(survey, llm_client=mock_llm)
    mock_llm.create_completion.assert_called_once()


def test_validate_survey_llm_cross_question_issues():
    mock_llm = Mock(spec=LLMClient)
    mock_llm.create_completion.return_value = json.dumps(
        [
            {
                "code": "redundant",
                "severity": "info",
                "message": "Overlap with q1.",
                "question_id": "q2",
            }
        ]
    )
    survey = _make_survey([_open_q("q1"), _open_q("q2")])
    issues = validate_survey(survey, llm_client=mock_llm)
    cross_issues = [i for i in issues if i.code == "redundant"]
    assert len(cross_issues) == 1
    assert cross_issues[0].question_id == "q2"


def test_validate_survey_returns_validation_issue_objects():
    survey = _make_survey([_choice_q("q1", n_opts=2)])
    issues = validate_survey(survey)
    assert all(isinstance(i, ValidationIssue) for i in issues)


def test_validate_survey_empty_survey():
    survey = Survey(id="s1", title="Empty", sections=[])
    issues = validate_survey(survey)
    assert issues == []


# ---------------------------------------------------------------------------
# Tier 1: social_desirability
# ---------------------------------------------------------------------------


def test_social_desirability_do_you_regularly():
    q = _open_q(text="Do you regularly submit your reports on time?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "social_desirability" in codes


def test_social_desirability_do_you_always():
    q = _open_q(text="Do you always follow safety procedures?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "social_desirability" in codes


def test_social_desirability_neutral_question_not_flagged():
    q = _open_q(text="How often do you submit your reports?")
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "social_desirability" not in codes


# ---------------------------------------------------------------------------
# Tier 1: missing_neutral_option
# ---------------------------------------------------------------------------


def test_missing_neutral_option_even_no_neutral():
    q = _choice_q(n_opts=4, opt_texts=["Agree", "Somewhat agree", "Somewhat disagree", "Disagree"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "missing_neutral_option" in codes


def test_missing_neutral_option_even_with_neutral_label():
    q = _choice_q(n_opts=4, opt_texts=["Agree", "Somewhat agree", "Neutral", "Disagree"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "missing_neutral_option" not in codes


def test_missing_neutral_option_odd_count_not_flagged():
    q = _choice_q(n_opts=5)
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "missing_neutral_option" not in codes


def test_missing_neutral_option_no_opinion_counts_as_neutral():
    q = _choice_q(n_opts=4, opt_texts=["Agree", "Somewhat agree", "No opinion", "Disagree"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "missing_neutral_option" not in codes


# ---------------------------------------------------------------------------
# Tier 1: unbalanced_anchors
# ---------------------------------------------------------------------------


def test_unbalanced_anchors_all_positive():
    q = _choice_q(n_opts=4, opt_texts=["Excellent", "Good", "Great", "Better"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "unbalanced_anchors" in codes


def test_unbalanced_anchors_all_negative():
    q = _choice_q(n_opts=3, opt_texts=["Terrible", "Bad", "Poor"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "unbalanced_anchors" in codes


def test_unbalanced_anchors_balanced_scale_not_flagged():
    q = _choice_q(
        n_opts=5,
        opt_texts=["Strongly agree", "Agree", "Neutral", "Disagree", "Strongly disagree"],
    )
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "unbalanced_anchors" not in codes


def test_unbalanced_anchors_fewer_than_3_options_not_flagged():
    q = _choice_q(n_opts=2, opt_texts=["Good", "Excellent"])
    issues = validate_question(q)
    codes = [i.code for i in issues]
    assert "unbalanced_anchors" not in codes


# ---------------------------------------------------------------------------
# _check_survey_tier1: survey_fatigue
# ---------------------------------------------------------------------------


def _make_large_survey(n_questions: int) -> Survey:
    questions = [_open_q(qid=f"q{i}", text=f"Question {i}?") for i in range(n_questions)]
    return _make_survey(questions)


def test_survey_fatigue_fires_above_threshold():
    survey = _make_large_survey(31)
    issues = _check_survey_tier1(survey)
    codes = [i.code for i in issues]
    assert "survey_fatigue" in codes
    assert issues[0].question_id == "survey"
    assert issues[0].severity == "warning"


def test_survey_fatigue_does_not_fire_at_threshold():
    survey = _make_large_survey(30)
    issues = _check_survey_tier1(survey)
    assert issues == []


def test_survey_fatigue_via_validate_survey():
    survey = _make_large_survey(31)
    issues = validate_survey(survey)
    codes = [i.code for i in issues]
    assert "survey_fatigue" in codes


# ---------------------------------------------------------------------------
# Advisory note integration tests (conversation.py + validation_engine.py)
# ---------------------------------------------------------------------------


def _survey_dict_with_social_desirability() -> dict:
    return {
        "id": "s1",
        "title": "Survey",
        "description": "",
        "metadata": {},
        "sections": [
            {
                "id": "sec1",
                "title": "Section",
                "description": "",
                "order": 0,
                "metadata": {},
                "questions": [
                    {
                        "id": "q1",
                        "text": "Do you always follow the code of conduct?",
                        "type": "open_ended",
                        "answer_options": [],
                        "order": 0,
                        "required": True,
                        "min_value": None,
                        "max_value": None,
                        "step": None,
                        "metadata": {},
                    }
                ],
            }
        ],
    }


def test_advisory_note_appended_for_new_issue(tmp_path):
    from unittest.mock import Mock

    from m_chat.conversation import execute_chat_turn

    mock_llm = Mock()
    mock_llm.create_completion.return_value = (
        f"Here is the updated survey."
        f"<survey_update>{json.dumps(_survey_dict_with_social_desirability())}</survey_update>"
    )

    text, survey_updated = execute_chat_turn(
        session_id="sess1",
        message="Add a conduct question.",
        base_path=str(tmp_path),
        llm_client=mock_llm,
        conversation=[],
    )

    assert survey_updated is True
    assert "was this intentional?" in text


def test_advisory_note_not_shown_for_preexisting_issue(tmp_path):
    from unittest.mock import Mock

    from m_chat.conversation import execute_chat_turn
    from m_chat.session import save_draft_survey

    session_id = "sess2"
    existing_q = Question(
        id="q1",
        text="Do you always follow the code of conduct?",
        type=QuestionType.OPEN_ENDED,
    )
    existing_survey = Survey(
        id="s1",
        title="Survey",
        sections=[Section(id="sec1", title="Section", questions=[existing_q])],
    )
    save_draft_survey(str(tmp_path), session_id, existing_survey)

    mock_llm = Mock()
    mock_llm.create_completion.return_value = f"No changes.<survey_update>{json.dumps(_survey_dict_with_social_desirability())}</survey_update>"

    text, survey_updated = execute_chat_turn(
        session_id=session_id,
        message="Review the survey.",
        base_path=str(tmp_path),
        llm_client=mock_llm,
        conversation=[],
    )

    assert survey_updated is True
    assert "was this intentional?" not in text


def test_advisory_note_not_shown_for_info_only_issue(tmp_path):
    """An info-severity new issue (e.g. missing_neutral_option) must not trigger an advisory note."""
    from unittest.mock import Mock

    from m_chat.conversation import execute_chat_turn

    # single_choice with 4 even options and no neutral label → missing_neutral_option (info only)
    survey_dict = {
        "id": "s1",
        "title": "Survey",
        "description": "",
        "metadata": {},
        "sections": [
            {
                "id": "sec1",
                "title": "Section",
                "description": "",
                "order": 0,
                "metadata": {},
                "questions": [
                    {
                        "id": "q1",
                        "text": "How satisfied are you?",
                        "type": "single_choice",
                        "answer_options": [
                            {"id": "o1", "text": "Very satisfied", "value": None},
                            {"id": "o2", "text": "Satisfied", "value": None},
                            {"id": "o3", "text": "Dissatisfied", "value": None},
                            {"id": "o4", "text": "Very dissatisfied", "value": None},
                        ],
                        "order": 0,
                        "required": True,
                        "min_value": None,
                        "max_value": None,
                        "step": None,
                        "metadata": {},
                    }
                ],
            }
        ],
    }

    mock_llm = Mock()
    mock_llm.create_completion.return_value = (
        f"Updated.<survey_update>{json.dumps(survey_dict)}</survey_update>"
    )

    text, survey_updated = execute_chat_turn(
        session_id="sess_info",
        message="Add a satisfaction question.",
        base_path=str(tmp_path),
        llm_client=mock_llm,
        conversation=[],
    )

    assert survey_updated is True
    assert "was this intentional?" not in text
