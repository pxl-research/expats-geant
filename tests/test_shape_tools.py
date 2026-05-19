"""Unit tests for shape_api.tools — the chat-turn tool dispatcher."""

import json

import pytest

from m_shared.models.survey import Survey
from shape_api.session import save_draft_survey
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
