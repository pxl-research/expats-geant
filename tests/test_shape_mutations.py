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
    apply_update_question,
    apply_update_section,
)


def _question(qid: str, order: int = 0) -> Question:
    return Question(id=qid, text=f"Question {qid}", type=QuestionType.OPEN_ENDED, order=order)


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


class TestMovePreservesId:
    def test_delete_then_add_keeps_question_id(self):
        survey = Survey(
            id="s1",
            title="T",
            sections=[_section("a", "q1"), _section("b")],
        )
        moved = survey.sections[0].questions[0]
        after_delete = apply_delete_question(survey, "q1")
        after_add = apply_add_question(after_delete, "b", moved)
        assert [q.id for q in after_add.sections[0].questions] == []
        assert [q.id for q in after_add.sections[1].questions] == ["q1"]
