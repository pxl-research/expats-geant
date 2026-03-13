"""Unit tests for LimeSurveyAdapter.fetch_survey and QualtricsAdapter.fetch_survey."""

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests

from m_shared.adapters.limesurvey import LimeSurveyAdapter
from m_shared.adapters.qualtrics import QualtricsAdapter

# ---------------------------------------------------------------------------
# Minimal LSS XML fixture
# ---------------------------------------------------------------------------

_LSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>123</sid>
    <surveyls_title>Test Survey</surveyls_title>
    <surveyls_description></surveyls_description>
  </row></rows></surveys>
  <groups><rows><row>
    <gid>1</gid>
    <group_name>Section 1</group_name>
    <description></description>
    <group_order>0</group_order>
  </row></rows></groups>
  <questions><rows><row>
    <qid>10</qid>
    <gid>1</gid>
    <type>T</type>
    <question>What is your name?</question>
    <mandatory>N</mandatory>
    <question_order>1</question_order>
    <parent_qid>0</parent_qid>
  </row></rows></questions>
  <answers><rows></rows></answers>
</document>
"""

_LSS_B64 = base64.b64encode(_LSS_XML.encode()).decode()

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


class TestLimeSurveyFetchSurvey:
    def _make_adapter(self, **kwargs):
        defaults = {"api_url": "http://ls.example.com/rpc", "username": "admin", "password": "pw"}
        defaults.update(kwargs)
        return LimeSurveyAdapter(**defaults)

    @patch("requests.post")
    def test_fetch_survey_success(self, mock_post):
        """RC2 returns base64 LSS → valid Survey."""
        # get_session_key → "key123", export_survey → base64 LSS, release → "OK"
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": "key123", "error": None, "id": 1}),
            MagicMock(status_code=200, json=lambda: {"result": _LSS_B64, "error": None, "id": 1}),
            MagicMock(status_code=200, json=lambda: {"result": "OK", "error": None, "id": 1}),
        ]
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("123")
        assert survey.title == "Test Survey"
        assert survey.id == "123"
        assert len(survey.sections) == 1
        assert len(survey.sections[0].questions) == 1

    def test_fetch_survey_missing_credentials(self):
        """Missing credentials raises ValueError before any network call."""
        adapter = LimeSurveyAdapter(api_url=None, username=None, password=None)
        with pytest.raises(ValueError, match="must be set"):
            adapter.fetch_survey("123")

    @patch("requests.post")
    def test_fetch_survey_network_error(self, mock_post):
        """Network failure on get_session_key raises RuntimeError."""
        mock_post.side_effect = requests.RequestException("connection refused")
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError, match="LimeSurvey RPC call"):
            adapter.fetch_survey("123")

    @patch("requests.post")
    def test_fetch_survey_rpc_error(self, mock_post):
        """export_survey returning error status raises RuntimeError."""
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"result": "key123", "error": None, "id": 1}),
            MagicMock(
                status_code=200,
                json=lambda: {"result": {"status": "Survey not found"}, "error": None, "id": 1},
            ),
            MagicMock(status_code=200, json=lambda: {"result": "OK", "error": None, "id": 1}),
        ]
        adapter = self._make_adapter()
        with pytest.raises(RuntimeError, match="export_survey failed"):
            adapter.fetch_survey("999")


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
        """GET /v3/surveys/{id} returns QSF JSON → valid Survey."""
        # Qualtrics returns the full QSF document directly
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: _QSF,
        )
        mock_get.return_value.raise_for_status = MagicMock()
        adapter = self._make_adapter()
        survey = adapter.fetch_survey("SV_abc123")
        assert survey.title == "Test Survey"
        assert survey.id == "SV_abc123"
        assert len(survey.sections) == 1
        assert len(survey.sections[0].questions) == 1

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
