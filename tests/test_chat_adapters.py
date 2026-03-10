"""Unit tests for create_survey() on all platform adapters.

Covers:
- Base class: create_survey() raises NotImplementedError
- LimeSurvey: create_survey() via RC2 API, error handling, credential check
- Qualtrics: create_survey() via v3 API, error handling, credential check
- SurveyMonkey: create_survey() delegates to export_survey()
- QTI: create_survey() delegates to export_survey()
- All four adapters include "create" in capabilities()
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from m_shared.adapters.base import SurveyAdapter
from m_shared.adapters.limesurvey import LimeSurveyAdapter
from m_shared.adapters.qti import QTIAdapter
from m_shared.adapters.qualtrics import QualtricsAdapter
from m_shared.adapters.surveymonkey import SurveyMonkeyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def open_ended_survey():
    """Minimal survey with one open-ended question."""
    return Survey(
        id="test_survey",
        title="Test Survey",
        description="A test survey",
        sections=[
            Section(
                id="sec1",
                title="Section 1",
                description="First section",
                questions=[
                    Question(
                        id="q1",
                        text="How are you?",
                        type=QuestionType.OPEN_ENDED,
                        order=0,
                        answer_options=[],
                        required=False,
                        metadata={},
                    ),
                ],
                order=0,
                metadata={},
            )
        ],
        metadata={},
    )


@pytest.fixture
def multi_question_survey():
    """Survey with multiple question types across two sections."""
    return Survey(
        id="multi_survey",
        title="Multi-Type Survey",
        description="",
        sections=[
            Section(
                id="sec1",
                title="Section 1",
                description="",
                questions=[
                    Question(
                        id="q1",
                        text="Describe your experience",
                        type=QuestionType.OPEN_ENDED,
                        order=0,
                        answer_options=[],
                        required=False,
                        metadata={},
                    ),
                    Question(
                        id="q2",
                        text="Choose your preference",
                        type=QuestionType.SINGLE_CHOICE,
                        order=1,
                        answer_options=[
                            AnswerOption(id="a", text="Option A", value="A", metadata={}),
                            AnswerOption(id="b", text="Option B", value="B", metadata={}),
                        ],
                        required=True,
                        metadata={},
                    ),
                ],
                order=0,
                metadata={},
            ),
            Section(
                id="sec2",
                title="Section 2",
                description="",
                questions=[
                    Question(
                        id="q3",
                        text="Rate your satisfaction",
                        type=QuestionType.SLIDER,
                        order=0,
                        answer_options=[],
                        required=False,
                        min_value=0.0,
                        max_value=10.0,
                        step=1.0,
                        metadata={},
                    ),
                ],
                order=1,
                metadata={},
            ),
        ],
        metadata={},
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class TestBaseAdapterCreateSurvey:
    def test_create_survey_raises_not_implemented(self, open_ended_survey):
        """Base class default raises NotImplementedError."""

        class MinimalAdapter(SurveyAdapter):
            def import_survey(self, raw):
                pass

            def export_survey(self, survey):
                return ""

            def capabilities(self):
                return {"import", "export"}

        adapter = MinimalAdapter()
        with pytest.raises(NotImplementedError, match="does not support create_survey"):
            adapter.create_survey(open_ended_survey)

    def test_not_implemented_message_includes_class_name(self, open_ended_survey):
        class MyCustomAdapter(SurveyAdapter):
            def import_survey(self, raw):
                pass

            def export_survey(self, survey):
                return ""

            def capabilities(self):
                return {"import", "export"}

        adapter = MyCustomAdapter()
        with pytest.raises(NotImplementedError, match="MyCustomAdapter"):
            adapter.create_survey(open_ended_survey)


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilitiesIncludeCreate:
    def test_limesurvey_has_create(self):
        assert "create" in LimeSurveyAdapter().capabilities()

    def test_qualtrics_has_create(self):
        assert "create" in QualtricsAdapter().capabilities()

    def test_surveymonkey_has_create(self):
        assert "create" in SurveyMonkeyAdapter().capabilities()

    def test_qti_has_create(self):
        assert "create" in QTIAdapter().capabilities()

    def test_limesurvey_retains_other_capabilities(self):
        caps = LimeSurveyAdapter().capabilities()
        assert {"import", "export", "submit"}.issubset(caps)

    def test_qualtrics_retains_other_capabilities(self):
        caps = QualtricsAdapter().capabilities()
        assert {"import", "export", "submit"}.issubset(caps)

    def test_surveymonkey_retains_other_capabilities(self):
        caps = SurveyMonkeyAdapter().capabilities()
        assert {"import", "export"}.issubset(caps)

    def test_qti_retains_other_capabilities(self):
        caps = QTIAdapter().capabilities()
        assert {"import", "export"}.issubset(caps)


# ---------------------------------------------------------------------------
# LimeSurvey create_survey
# ---------------------------------------------------------------------------


class TestLimeSurveyCreateSurvey:
    def _make_adapter(self):
        return LimeSurveyAdapter(
            api_url="http://lime.example.com/remotecontrol",
            username="admin",
            password="secret",
        )

    def _make_rpc_results(self, sid=42, gid=10, qids=(100,)):
        """Build a sequence of RPC return values for a single-section survey."""
        # get_session_key, add_survey, add_group, add_question..., release_session_key
        values = ["SESSION_KEY", sid, gid] + list(qids) + ["OK"]
        it = iter(values)
        return lambda method, params: next(it)

    def test_create_survey_returns_sid_as_string(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results(sid=42, gid=10, qids=(100,))
        with patch.object(adapter, "_rpc_call", side_effect=side_effect):
            result = adapter.create_survey(open_ended_survey)
        assert result == "42"

    def test_create_survey_calls_get_session_key_first(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results(sid=55)
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        assert mock_rpc.call_args_list[0][0][0] == "get_session_key"

    def test_create_survey_calls_add_survey(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        assert "add_survey" in method_names

    def test_create_survey_calls_add_group(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        assert "add_group" in method_names

    def test_create_survey_calls_add_question(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        assert "add_question" in method_names

    def test_create_survey_calls_release_session_key(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        assert "release_session_key" in method_names

    def test_create_survey_rpc_order(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        # Order: get_session_key → add_survey → add_group → add_question → release
        assert method_names.index("get_session_key") < method_names.index("add_survey")
        assert method_names.index("add_survey") < method_names.index("add_group")
        assert method_names.index("add_group") < method_names.index("add_question")
        assert method_names.index("add_question") < method_names.index("release_session_key")

    def test_create_survey_multi_question_calls_add_question_per_question(
        self, multi_question_survey
    ):
        adapter = self._make_adapter()
        # 2 sections: 1 group + 2 questions, 1 group + 1 question
        values = iter(["SK", 99, 1, 10, 11, 2, 20, "OK"])
        with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)) as mock_rpc:
            result = adapter.create_survey(multi_question_survey)
        method_names = [c[0][0] for c in mock_rpc.call_args_list]
        assert method_names.count("add_question") == 3  # q1, q2, q3
        assert method_names.count("add_group") == 2  # two sections
        assert result == "99"

    def test_create_survey_add_survey_params_include_title(self, open_ended_survey):
        adapter = self._make_adapter()
        side_effect = self._make_rpc_results()
        with patch.object(adapter, "_rpc_call", side_effect=side_effect) as mock_rpc:
            adapter.create_survey(open_ended_survey)
        add_survey_call = next(c for c in mock_rpc.call_args_list if c[0][0] == "add_survey")
        params = add_survey_call[0][1]
        assert open_ended_survey.title in params

    def test_add_survey_rc2_error_raises_runtime_error(self, open_ended_survey):
        adapter = self._make_adapter()
        values = iter(["SK", {"status": "Survey creation failed"}, "OK"])
        with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)):
            with pytest.raises(RuntimeError, match="add_survey failed"):
                adapter.create_survey(open_ended_survey)

    def test_add_group_rc2_error_raises_runtime_error(self, open_ended_survey):
        adapter = self._make_adapter()
        values = iter(["SK", 42, {"status": "Group creation failed"}, "OK"])
        with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)):
            with pytest.raises(RuntimeError, match="add_group failed"):
                adapter.create_survey(open_ended_survey)

    def test_add_question_rc2_error_raises_runtime_error(self, open_ended_survey):
        adapter = self._make_adapter()
        values = iter(["SK", 42, 10, {"status": "Question creation failed"}, "OK"])
        with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)):
            with pytest.raises(RuntimeError, match="add_question failed"):
                adapter.create_survey(open_ended_survey)

    def test_release_called_even_on_error(self, open_ended_survey):
        adapter = self._make_adapter()
        values = iter(["SK", {"status": "Error"}, "OK"])
        with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)) as mock_rpc:
            with pytest.raises(RuntimeError):
                adapter.create_survey(open_ended_survey)
        release_calls = [c for c in mock_rpc.call_args_list if c[0][0] == "release_session_key"]
        assert len(release_calls) == 1

    def test_missing_api_url_raises_value_error(self, open_ended_survey):
        adapter = LimeSurveyAdapter(username="admin", password="secret")
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_missing_username_raises_value_error(self, open_ended_survey):
        adapter = LimeSurveyAdapter(api_url="http://lime.example.com", password="secret")
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_missing_password_raises_value_error(self, open_ended_survey):
        adapter = LimeSurveyAdapter(api_url="http://lime.example.com", username="admin")
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_no_credentials_raises_value_error(self, open_ended_survey):
        adapter = LimeSurveyAdapter()
        with pytest.raises(ValueError):
            adapter.create_survey(open_ended_survey)

    def test_different_survey_ids_returned_correctly(self, open_ended_survey):
        adapter = self._make_adapter()
        for expected_sid in (1, 100, 99999):
            values = iter(["SK", expected_sid, 1, 1, "OK"])
            with patch.object(adapter, "_rpc_call", side_effect=lambda m, p: next(values)):
                result = adapter.create_survey(open_ended_survey)
            assert result == str(expected_sid)


# ---------------------------------------------------------------------------
# Qualtrics create_survey
# ---------------------------------------------------------------------------


class TestQualtricsCreateSurvey:
    def _make_adapter(self):
        return QualtricsAdapter(api_token="test-token", datacenter_id="iad1")

    def _mock_response(self, survey_id="SV_abc123"):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {"SurveyID": survey_id}}
        return mock_resp

    def test_create_survey_returns_survey_id(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = self._mock_response("SV_test123")
        with patch("m_shared.adapters.qualtrics.requests.post", return_value=mock_resp):
            result = adapter.create_survey(open_ended_survey)
        assert result == "SV_test123"

    def test_create_survey_posts_to_surveys_url(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = self._mock_response()
        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.create_survey(open_ended_survey)
        call_args = mock_post.call_args
        url = call_args[0][0]
        assert "surveys" in url
        assert "iad1" in url

    def test_create_survey_sends_qsf_payload(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = self._mock_response()
        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.create_survey(open_ended_survey)
        call_kwargs = mock_post.call_args[1]
        assert "json" in call_kwargs
        qsf = call_kwargs["json"]
        assert "SurveyEntry" in qsf
        assert "SurveyElements" in qsf

    def test_create_survey_includes_api_token_header(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = self._mock_response()
        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.create_survey(open_ended_survey)
        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("X-API-TOKEN") == "test-token"

    def test_create_survey_http_error_propagated(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        with patch("m_shared.adapters.qualtrics.requests.post", return_value=mock_resp):
            with pytest.raises(requests.HTTPError):
                adapter.create_survey(open_ended_survey)

    def test_create_survey_missing_survey_id_raises_runtime_error(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": {}}  # no SurveyID
        with patch("m_shared.adapters.qualtrics.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="SurveyID"):
                adapter.create_survey(open_ended_survey)

    def test_create_survey_missing_result_key_raises_runtime_error(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}  # no "result" key
        with patch("m_shared.adapters.qualtrics.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="SurveyID"):
                adapter.create_survey(open_ended_survey)

    def test_create_survey_no_credentials_raises_value_error(self, open_ended_survey):
        adapter = QualtricsAdapter()
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_create_survey_missing_token_raises_value_error(self, open_ended_survey):
        adapter = QualtricsAdapter(datacenter_id="iad1")
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_create_survey_missing_datacenter_raises_value_error(self, open_ended_survey):
        adapter = QualtricsAdapter(api_token="tok")
        with pytest.raises(ValueError, match="must be set"):
            adapter.create_survey(open_ended_survey)

    def test_create_survey_qsf_includes_survey_title(self, open_ended_survey):
        adapter = self._make_adapter()
        mock_resp = self._mock_response()
        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.create_survey(open_ended_survey)
        qsf = mock_post.call_args[1]["json"]
        assert open_ended_survey.title in qsf.get("SurveyEntry", {}).get("SurveyName", "")


# ---------------------------------------------------------------------------
# SurveyMonkey create_survey
# ---------------------------------------------------------------------------


class TestSurveyMonkeyCreateSurvey:
    def test_create_survey_returns_same_as_export(self, open_ended_survey):
        adapter = SurveyMonkeyAdapter()
        assert adapter.create_survey(open_ended_survey) == adapter.export_survey(open_ended_survey)

    def test_create_survey_returns_json_string(self, open_ended_survey):
        adapter = SurveyMonkeyAdapter()
        result = adapter.create_survey(open_ended_survey)
        data = json.loads(result)
        assert data["title"] == open_ended_survey.title

    def test_create_survey_includes_sections(self, multi_question_survey):
        adapter = SurveyMonkeyAdapter()
        result = json.loads(adapter.create_survey(multi_question_survey))
        assert len(result["pages"]) == 2

    def test_create_survey_consistent_with_multiple_calls(self, open_ended_survey):
        adapter = SurveyMonkeyAdapter()
        assert adapter.create_survey(open_ended_survey) == adapter.create_survey(open_ended_survey)


# ---------------------------------------------------------------------------
# QTI create_survey
# ---------------------------------------------------------------------------


class TestQTICreateSurvey:
    def test_create_survey_returns_same_as_export(self, open_ended_survey):
        adapter = QTIAdapter()
        assert adapter.create_survey(open_ended_survey) == adapter.export_survey(open_ended_survey)

    def test_create_survey_returns_xml_string(self, open_ended_survey):
        adapter = QTIAdapter()
        result = adapter.create_survey(open_ended_survey)
        assert "<assessmentTest" in result

    def test_create_survey_includes_survey_title(self, open_ended_survey):
        adapter = QTIAdapter()
        result = adapter.create_survey(open_ended_survey)
        assert open_ended_survey.title in result

    def test_create_survey_consistent_with_multiple_calls(self, open_ended_survey):
        adapter = QTIAdapter()
        assert adapter.create_survey(open_ended_survey) == adapter.create_survey(open_ended_survey)
