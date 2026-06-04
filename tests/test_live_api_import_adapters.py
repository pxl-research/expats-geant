"""Unit tests for LimeSurveyAdapter.fetch_survey and QualtricsAdapter.fetch_survey."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from m_shared.adapters.limesurvey import LimeSurveyAdapter
from m_shared.adapters.qualtrics import QualtricsAdapter

# ---------------------------------------------------------------------------
# LimeSurvey RC2 fixtures — shaped exactly like list_groups / list_questions
# / get_survey_properties / get_question_properties responses from LS 6.17.4.
# ---------------------------------------------------------------------------

_SURVEY_PROPS = {
    "sid": 123,
    "language": "en",
    "active": "N",
}

_LANG_PROPS = {
    "surveyls_title": "Test Survey",
    "surveyls_description": "",
    "surveyls_language": "en",
}

_LIST_GROUPS = [
    {"gid": 1, "group_name": "Section 1", "description": "", "group_order": 0},
]

_LIST_QUESTIONS_TEXT_ONLY = [
    {
        "qid": 10,
        "gid": 1,
        "parent_qid": 0,
        "type": "T",
        "title": "Q1",
        "question": "What is your name?",
        "mandatory": "N",
        "question_order": 1,
    }
]

# ---------------------------------------------------------------------------
# Minimal QSF JSON fixture
# ---------------------------------------------------------------------------

_QSF = {
    "SurveyEntry": {
        "SurveyID": "SV_abc123",
        "SurveyName": "Test Survey",
        "SurveyDescription": "",
    },
    "SurveyElements": [
        {
            "Element": "FL",
            "Payload": {
                "Flow": [{"Type": "Block", "ID": "BL_1", "FlowID": "FL_BL_1"}],
                "FlowID": "FL_1",
                "Type": "Root",
            },
        },
        {
            "Element": "BL",
            "Payload": [
                {
                    "Type": "Default",
                    "Description": "Block 1",
                    "ID": "BL_1",
                    "BlockElements": [{"Type": "Question", "QuestionID": "QID1"}],
                }
            ],
        },
        {
            "Element": "SQ",
            "Payload": {
                "QuestionID": "QID1",
                "QuestionText": "What is your role?",
                "QuestionType": "TE",
                "Selector": "ML",
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# LimeSurvey tests
# ---------------------------------------------------------------------------


def _rpc_response(result):
    """Build a MagicMock that mimics a successful LimeSurvey RC2 JSON response."""
    return MagicMock(status_code=200, json=lambda: {"result": result, "error": None, "id": 1})


class TestLimeSurveyFetchSurvey:
    """LimeSurvey fetch_survey composes get_survey_properties + list_groups +
    list_questions + (conditional) get_question_properties. The old
    ``export_survey`` RPC was removed in LimeSurvey 6."""

    def _make_adapter(self, **kwargs):
        defaults = {"api_url": "http://ls.example.com/rpc", "username": "admin", "password": "pw"}
        defaults.update(kwargs)
        return LimeSurveyAdapter(**defaults)

    @patch("requests.post")
    def test_fetch_survey_success_text_question(self, mock_post):
        """A text-only survey produces no get_question_properties call."""
        mock_post.side_effect = [
            _rpc_response("key123"),
            _rpc_response(_SURVEY_PROPS),
            _rpc_response(_LANG_PROPS),
            _rpc_response(_LIST_GROUPS),
            _rpc_response(_LIST_QUESTIONS_TEXT_ONLY),
            _rpc_response("OK"),
        ]
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("123")
        assert survey.title == "Test Survey"
        assert survey.id == "123"
        assert len(survey.sections) == 1
        assert len(survey.sections[0].questions) == 1
        assert survey.sections[0].questions[0].text == "What is your name?"
        # Text type does not need get_question_properties
        methods_called = [c.kwargs["data"] for c in mock_post.call_args_list]
        assert not any('"get_question_properties"' in d for d in methods_called)

    @patch("requests.post")
    def test_fetch_survey_m_question_uses_subquestion_rows(self, mock_post):
        """M-question options come from sub-question rows in list_questions
        — no get_question_properties needed for type M/P."""
        list_questions = [
            {
                "qid": 5001,
                "gid": 1,
                "parent_qid": 0,
                "type": "M",
                "title": "QM1",
                "question": "Which colors do you like?",
                "mandatory": "N",
                "question_order": 1,
            },
            {
                "qid": 5002,
                "gid": 1,
                "parent_qid": 5001,
                "type": "T",
                "title": "A1",
                "question": "Red",
                "question_order": 1,
            },
            {
                "qid": 5003,
                "gid": 1,
                "parent_qid": 5001,
                "type": "T",
                "title": "A2",
                "question": "Green",
                "question_order": 2,
            },
        ]
        mock_post.side_effect = [
            _rpc_response("key123"),
            _rpc_response(_SURVEY_PROPS),
            _rpc_response(_LANG_PROPS),
            _rpc_response(_LIST_GROUPS),
            _rpc_response(list_questions),
            _rpc_response("OK"),
        ]
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("123")
        question = survey.sections[0].questions[0]
        assert [opt.value for opt in question.answer_options] == ["A1", "A2"]
        assert [opt.text for opt in question.answer_options] == ["Red", "Green"]

    @patch("requests.post")
    def test_fetch_survey_l_question_uses_get_question_properties(self, mock_post):
        """L-type (radio) options come from get_question_properties.answeroptions."""
        list_questions = [
            {
                "qid": 200,
                "gid": 1,
                "parent_qid": 0,
                "type": "L",
                "title": "QL1",
                "question": "Pick one",
                "mandatory": "Y",
                "question_order": 1,
            }
        ]
        q_props = {
            "answeroptions": {
                "A1": {"answer": "Yes", "order": 1},
                "A2": {"answer": "No", "order": 2},
            },
            "attributes": {},
        }
        mock_post.side_effect = [
            _rpc_response("key123"),
            _rpc_response(_SURVEY_PROPS),
            _rpc_response(_LANG_PROPS),
            _rpc_response(_LIST_GROUPS),
            _rpc_response(list_questions),
            _rpc_response(q_props),
            _rpc_response("OK"),
        ]
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("123")
        question = survey.sections[0].questions[0]
        assert [opt.value for opt in question.answer_options] == ["A1", "A2"]
        assert [opt.text for opt in question.answer_options] == ["Yes", "No"]
        assert question.required is True

    def test_fetch_survey_missing_credentials(self):
        """Missing credentials raises ValueError before any network call."""
        adapter = LimeSurveyAdapter(api_url=None, username=None, password=None)
        with pytest.raises(ValueError, match="must be set"):
            adapter.fetch_survey("123")

    @patch("requests.post")
    def test_fetch_survey_network_error(self, mock_post):
        """Network failure on the first RPC call raises RuntimeError."""
        mock_post.side_effect = requests.RequestException("connection refused")
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError, match="LimeSurvey RPC call"):
            adapter.fetch_survey("123")

    @patch("requests.post")
    def test_fetch_survey_rpc_error_surfaces_method_name(self, mock_post):
        """An RC2 ``{status: ...}`` failure mentions the offending method."""
        mock_post.side_effect = [
            _rpc_response("key123"),
            _rpc_response({"status": "Survey not found"}),
            _rpc_response("OK"),
        ]
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError, match="get_survey_properties failed"):
            adapter.fetch_survey("999")

    @patch("requests.post")
    def test_fetch_survey_releases_session_on_error(self, mock_post):
        """The session key is released even when an intermediate RPC call fails."""
        mock_post.side_effect = [
            _rpc_response("key123"),
            _rpc_response({"status": "Permission denied"}),
            _rpc_response("OK"),
        ]
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError):
            adapter.fetch_survey("123")
        last_call = mock_post.call_args_list[-1]
        assert '"release_session_key"' in last_call.kwargs["data"]


# ---------------------------------------------------------------------------
# Qualtrics tests
# ---------------------------------------------------------------------------


class TestQualtricsFetchSurvey:
    def _make_adapter(self, **kwargs):
        defaults = {"api_token": "token123", "datacenter_id": "iad1"}
        defaults.update(kwargs)
        return QualtricsAdapter(**defaults)

    @patch("requests.get")
    def test_fetch_survey_success(self, mock_get):
        """GET /v3/surveys/{id} returns v3 envelope → valid Survey."""
        # Real Qualtrics v3 API wraps the QSF in a {result, meta} envelope
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": _QSF, "meta": {"httpStatus": "200 - OK"}},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("SV_abc123")
        assert survey.title == "Test Survey"
        assert survey.id == "SV_abc123"
        assert len(survey.sections) == 1
        assert len(survey.sections[0].questions) == 1

    @patch("requests.get")
    def test_fetch_survey_success_raw_fallback(self, mock_get):
        """GET /v3/surveys/{id} returns raw QSF (no envelope) → valid Survey."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _QSF,
        )
        mock_get.return_value.raise_for_status = MagicMock()
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("SV_abc123")
        assert survey.title == "Test Survey"
        assert len(survey.sections) == 1

    def test_fetch_survey_missing_credentials(self):
        """Missing credentials raises ValueError before any network call."""
        adapter = QualtricsAdapter(api_token=None, datacenter_id=None)
        with pytest.raises(ValueError, match="must be set"):
            adapter.fetch_survey("SV_abc123")

    @patch("requests.get")
    def test_fetch_survey_network_error(self, mock_get):
        """Network failure raises RuntimeError."""
        mock_get.side_effect = requests.RequestException("timeout")
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError, match="Qualtrics fetch_survey failed"):
            adapter.fetch_survey("SV_abc123")
