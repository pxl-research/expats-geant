"""Unit tests for shape_api.tools — the chat-turn tool dispatcher."""

import json

import pytest

from m_shared.models.survey import Survey
from shape_api.session import load_draft_survey, save_draft_survey
from shape_api.tools import GET_FULL_SURVEY_TOOL, NO_DRAFT_SENTINEL, dispatch_tool_call

_SURVEY_DICT = {
    "id": "s1",
    "title": "Test Survey",
    "description": "",
    "sections": [
        {
            "id": "sec1",
            "title": "Section 1",
            "description": "",
            "order": 0,
            "metadata": {},
            "questions": [
                {
                    "id": "q1",
                    "text": "How are you?",
                    "type": "open_ended",
                    "order": 0,
                    "answer_options": [],
                    "required": True,
                    "min_value": None,
                    "max_value": None,
                    "step": None,
                    "metadata": {},
                }
            ],
        }
    ],
    "metadata": {},
}


class TestGetFullSurveyDispatch:
    def test_returns_draft_json_when_draft_exists(self, tmp_path):
        sid = "sess_1"
        (tmp_path / sid).mkdir()
        save_draft_survey(str(tmp_path), sid, Survey(**_SURVEY_DICT))

        result_json = dispatch_tool_call(
            name="get_full_survey",
            arguments={},
            base_path=str(tmp_path),
            session_id=sid,
        )

        result_survey = Survey(**json.loads(result_json))
        assert result_survey.title == "Test Survey"
        assert result_survey.sections[0].questions[0].id == "q1"

    def test_returns_sentinel_when_no_draft(self, tmp_path):
        result = dispatch_tool_call(
            name="get_full_survey",
            arguments={},
            base_path=str(tmp_path),
            session_id="sess_missing",
        )
        assert result == NO_DRAFT_SENTINEL

    def test_unknown_tool_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown tool"):
            dispatch_tool_call(
                name="not_a_real_tool",
                arguments={},
                base_path=str(tmp_path),
                session_id="sess_x",
            )


class TestToolSchema:
    def test_schema_shape(self):
        assert GET_FULL_SURVEY_TOOL["type"] == "function"
        fn = GET_FULL_SURVEY_TOOL["function"]
        assert fn["name"] == "get_full_survey"
        assert fn["parameters"] == {"type": "object", "properties": {}, "required": []}
        assert "description" in fn and len(fn["description"]) > 0


def _seed(tmp_path, sid: str = "sess_m") -> str:
    (tmp_path / sid).mkdir()
    save_draft_survey(str(tmp_path), sid, Survey(**_SURVEY_DICT))
    return sid


def _dispatch(tmp_path, sid, name, arguments):
    return json.loads(
        dispatch_tool_call(name=name, arguments=arguments, base_path=str(tmp_path), session_id=sid)
    )


_NEW_QUESTION = {"id": "q2", "text": "New?", "type": "open_ended"}


class TestMutationDispatchHappyPath:
    def test_init_survey(self, tmp_path):
        sid = "sess_init"
        (tmp_path / sid).mkdir()
        other = {**_SURVEY_DICT, "title": "Fresh", "sections": []}
        result = _dispatch(tmp_path, sid, "init_survey", {"survey": other})
        assert result["status"] == "ok"
        assert load_draft_survey(str(tmp_path), sid).title == "Fresh"

    def test_add_section(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "add_section", {"section": {"id": "sec2", "title": "Two"}}
        )
        assert result["status"] == "ok"
        assert [s.id for s in load_draft_survey(str(tmp_path), sid).sections] == ["sec1", "sec2"]

    def test_update_section(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "update_section", {"section_id": "sec1", "patch": {"title": "Renamed"}}
        )
        assert result["status"] == "ok"
        assert load_draft_survey(str(tmp_path), sid).sections[0].title == "Renamed"

    def test_delete_section(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(tmp_path, sid, "delete_section", {"section_id": "sec1"})
        assert result["status"] == "ok"
        assert load_draft_survey(str(tmp_path), sid).sections == []

    def test_add_question(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "add_question", {"section_id": "sec1", "question": _NEW_QUESTION}
        )
        assert result["status"] == "ok"
        qids = [q.id for q in load_draft_survey(str(tmp_path), sid).sections[0].questions]
        assert qids == ["q1", "q2"]

    def test_update_question(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "update_question", {"question_id": "q1", "patch": {"text": "Changed"}}
        )
        assert result["status"] == "ok"
        assert load_draft_survey(str(tmp_path), sid).sections[0].questions[0].text == "Changed"

    def test_delete_question(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(tmp_path, sid, "delete_question", {"question_id": "q1"})
        assert result["status"] == "ok"
        assert load_draft_survey(str(tmp_path), sid).sections[0].questions == []

    def test_move_section(self, tmp_path):
        sid = _seed(tmp_path)
        _dispatch(tmp_path, sid, "add_section", {"section": {"id": "sec2", "title": "Two"}})
        result = _dispatch(
            tmp_path, sid, "move_section", {"section_id": "sec1", "after_id": "sec2"}
        )
        assert result["status"] == "ok"
        assert [s.id for s in load_draft_survey(str(tmp_path), sid).sections] == ["sec2", "sec1"]

    def test_move_question_within_section(self, tmp_path):
        sid = _seed(tmp_path)
        _dispatch(tmp_path, sid, "add_question", {"section_id": "sec1", "question": _NEW_QUESTION})
        result = _dispatch(tmp_path, sid, "move_question", {"question_id": "q1", "after_id": "q2"})
        assert result["status"] == "ok"
        qids = [q.id for q in load_draft_survey(str(tmp_path), sid).sections[0].questions]
        assert qids == ["q2", "q1"]

    def test_move_question_to_other_section(self, tmp_path):
        sid = _seed(tmp_path)
        _dispatch(tmp_path, sid, "add_section", {"section": {"id": "sec2", "title": "Two"}})
        result = _dispatch(
            tmp_path, sid, "move_question", {"question_id": "q1", "section_id": "sec2"}
        )
        assert result["status"] == "ok"
        survey = load_draft_survey(str(tmp_path), sid)
        assert [q.id for q in survey.sections[0].questions] == []
        assert [q.id for q in survey.sections[1].questions] == ["q1"]


class TestMutationDispatchErrors:
    def test_no_draft(self, tmp_path):
        result = _dispatch(
            tmp_path, "sess_empty", "add_section", {"section": {"id": "x", "title": "X"}}
        )
        assert result["status"] == "error"
        assert result["code"] == "no_survey_draft"

    def test_section_not_found(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(tmp_path, sid, "delete_section", {"section_id": "nope"})
        assert result["code"] == "section_not_found"

    def test_question_not_found(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "update_question", {"question_id": "nope", "patch": {"text": "x"}}
        )
        assert result["code"] == "question_not_found"

    def test_duplicate_id(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "add_section", {"section": {"id": "sec1", "title": "Dup"}}
        )
        assert result["code"] == "duplicate_id"

    def test_invalid_patch_from_extra_field(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "update_section", {"section_id": "sec1", "patch": {"questions": []}}
        )
        assert result["code"] == "invalid_patch"

    def test_patch_rejects_order_field(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(
            tmp_path, sid, "update_question", {"question_id": "q1", "patch": {"order": 5}}
        )
        assert result["code"] == "invalid_patch"

    def test_move_question_unknown_id(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(tmp_path, sid, "move_question", {"question_id": "nope"})
        assert result["code"] == "question_not_found"

    def test_move_section_unknown_id(self, tmp_path):
        sid = _seed(tmp_path)
        result = _dispatch(tmp_path, sid, "move_section", {"section_id": "nope"})
        assert result["code"] == "section_not_found"

    def test_unknown_tool_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown tool"):
            _dispatch(tmp_path, _seed(tmp_path), "not_a_tool", {})


class TestMutationValidationFeedback:
    def test_dense_section_surfaces_warning(self, tmp_path):
        sid = "sess_dense"
        (tmp_path / sid).mkdir()
        questions = [{"id": f"q{i}", "text": f"Q{i}?", "type": "open_ended"} for i in range(31)]
        survey = {
            **_SURVEY_DICT,
            "sections": [{"id": "big", "title": "Big", "questions": questions}],
        }
        save_draft_survey(str(tmp_path), sid, Survey(**survey))

        result = _dispatch(
            tmp_path, sid, "update_section", {"section_id": "big", "patch": {"title": "Big2"}}
        )
        assert result["status"] == "ok"
        codes = [i["code"] for i in result["validation_issues"]]
        assert "section_dense" in codes
