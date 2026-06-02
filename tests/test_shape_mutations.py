"""Unit tests for shape_api.mutations — pure survey mutation functions."""

import pytest

from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey
from shape_api.models import QuestionPatch, SectionPatch
from shape_api.mutations import (
    DuplicateId,
    InvalidPatch,
    NoSurveyDraft,
    QuestionNotFound,
    SectionNotFound,
    apply_add_question,
    apply_add_section,
    apply_delete_question,
    apply_delete_section,
    apply_init_survey,
    apply_move_question,
    apply_move_section,
    apply_update_question,
    apply_update_section,
)


def _question(qid: str) -> Question:
    return Question(id=qid, text=f"Question {qid}", type=QuestionType.OPEN_ENDED)


def _section(sid: str, *qids: str) -> Section:
    return Section(id=sid, title=f"Section {sid}", questions=[_question(q) for q in qids])


def _survey() -> Survey:
    return Survey(id="s1", title="Test", sections=[_section("sec1", "q1", "q2")])


class TestInitSurvey:
    def test_returns_survey(self):
        survey = _survey()
        assert apply_init_survey(survey) is survey


class TestAddSection:
    def test_appends_when_no_after_id(self):
        result = apply_add_section(_survey(), _section("sec2"))
        assert [s.id for s in result.sections] == ["sec1", "sec2"]

    def test_inserts_after_named_section(self):
        survey = Survey(id="s1", title="T", sections=[_section("a"), _section("b")])
        result = apply_add_section(survey, _section("mid"), after_id="a")
        assert [s.id for s in result.sections] == ["a", "mid", "b"]

    def test_duplicate_id_raises(self):
        with pytest.raises(DuplicateId):
            apply_add_section(_survey(), _section("sec1"))

    def test_no_draft_raises(self):
        with pytest.raises(NoSurveyDraft):
            apply_add_section(None, _section("sec1"))


class TestUpdateSection:
    def test_patches_only_set_fields(self):
        result = apply_update_section(_survey(), "sec1", SectionPatch(title="Renamed"))
        assert result.sections[0].title == "Renamed"
        assert [q.id for q in result.sections[0].questions] == ["q1", "q2"]

    def test_unknown_section_raises(self):
        with pytest.raises(SectionNotFound):
            apply_update_section(_survey(), "nope", SectionPatch(title="x"))

    def test_questions_field_forbidden_at_patch_construction(self):
        with pytest.raises(ValueError):
            SectionPatch.model_validate({"questions": []})


class TestDeleteSection:
    def test_removes_section(self):
        survey = Survey(id="s1", title="T", sections=[_section("a"), _section("b")])
        result = apply_delete_section(survey, "a")
        assert [s.id for s in result.sections] == ["b"]

    def test_unknown_section_raises(self):
        with pytest.raises(SectionNotFound):
            apply_delete_section(_survey(), "nope")


class TestAddQuestion:
    def test_appends_to_section(self):
        result = apply_add_question(_survey(), "sec1", _question("q3"))
        assert [q.id for q in result.sections[0].questions] == ["q1", "q2", "q3"]

    def test_inserts_after_named_question(self):
        result = apply_add_question(_survey(), "sec1", _question("mid"), after_id="q1")
        assert [q.id for q in result.sections[0].questions] == ["q1", "mid", "q2"]

    def test_unknown_section_raises(self):
        with pytest.raises(SectionNotFound):
            apply_add_question(_survey(), "nope", _question("q3"))

    def test_duplicate_question_id_raises(self):
        with pytest.raises(DuplicateId):
            apply_add_question(_survey(), "sec1", _question("q1"))


class TestUpdateQuestion:
    def test_patches_text(self):
        result = apply_update_question(_survey(), "q1", QuestionPatch(text="New text"))
        assert result.sections[0].questions[0].text == "New text"

    def test_unknown_question_raises(self):
        with pytest.raises(QuestionNotFound):
            apply_update_question(_survey(), "nope", QuestionPatch(text="x"))

    def test_invalid_merge_raises_invalid_patch(self):
        # Switching to slider without min/max violates the Question model validator.
        with pytest.raises(InvalidPatch):
            apply_update_question(_survey(), "q1", QuestionPatch(type=QuestionType.SLIDER))


class TestDeleteQuestion:
    def test_removes_question(self):
        result = apply_delete_question(_survey(), "q1")
        assert [q.id for q in result.sections[0].questions] == ["q2"]

    def test_unknown_question_raises(self):
        with pytest.raises(QuestionNotFound):
            apply_delete_question(_survey(), "nope")


class TestMoveQuestion:
    def test_reorder_within_section(self):
        survey = Survey(id="s1", title="T", sections=[_section("sec1", "q1", "q2", "q3")])
        result = apply_move_question(survey, "q1", after_id="q2")
        assert [q.id for q in result.sections[0].questions] == ["q2", "q1", "q3"]

    def test_omitting_after_id_moves_to_front(self):
        survey = Survey(id="s1", title="T", sections=[_section("sec1", "q1", "q2", "q3")])
        result = apply_move_question(survey, "q3")
        assert [q.id for q in result.sections[0].questions] == ["q3", "q1", "q2"]

    def test_cross_section_move_preserves_id_and_fields(self):
        survey = Survey(id="s1", title="T", sections=[_section("a", "q1"), _section("b", "q2")])
        result = apply_move_question(survey, "q1", after_id="q2", section_id="b")
        assert [q.id for q in result.sections[0].questions] == []
        assert [q.id for q in result.sections[1].questions] == ["q2", "q1"]
        moved = result.sections[1].questions[1]
        assert moved.text == "Question q1"

    def test_cross_section_move_to_front(self):
        survey = Survey(id="s1", title="T", sections=[_section("a", "q1"), _section("b", "q2")])
        result = apply_move_question(survey, "q1", after_id=None, section_id="b")
        assert [q.id for q in result.sections[1].questions] == ["q1", "q2"]

    def test_unknown_question_raises(self):
        with pytest.raises(QuestionNotFound):
            apply_move_question(_survey(), "nope")

    def test_unknown_target_section_raises(self):
        with pytest.raises(SectionNotFound):
            apply_move_question(_survey(), "q1", section_id="nope")

    def test_unknown_after_id_raises_and_leaves_draft_unchanged(self):
        survey = Survey(id="s1", title="T", sections=[_section("sec1", "q1", "q2", "q3")])
        with pytest.raises(QuestionNotFound):
            apply_move_question(survey, "q1", after_id="nope")
        assert [q.id for q in survey.sections[0].questions] == ["q1", "q2", "q3"]

    def test_no_draft_raises(self):
        with pytest.raises(NoSurveyDraft):
            apply_move_question(None, "q1")


class TestMoveSection:
    def test_reorder_after_named_section(self):
        survey = Survey(id="s1", title="T", sections=[_section("a"), _section("b"), _section("c")])
        result = apply_move_section(survey, "a", after_id="b")
        assert [s.id for s in result.sections] == ["b", "a", "c"]

    def test_omitting_after_id_moves_to_front(self):
        survey = Survey(id="s1", title="T", sections=[_section("a"), _section("b"), _section("c")])
        result = apply_move_section(survey, "c")
        assert [s.id for s in result.sections] == ["c", "a", "b"]

    def test_unknown_section_raises(self):
        with pytest.raises(SectionNotFound):
            apply_move_section(_survey(), "nope")

    def test_unknown_after_id_raises_and_leaves_draft_unchanged(self):
        survey = Survey(id="s1", title="T", sections=[_section("a"), _section("b"), _section("c")])
        with pytest.raises(SectionNotFound):
            apply_move_section(survey, "a", after_id="nope")
        assert [s.id for s in survey.sections] == ["a", "b", "c"]

    def test_no_draft_raises(self):
        with pytest.raises(NoSurveyDraft):
            apply_move_section(None, "sec1")
