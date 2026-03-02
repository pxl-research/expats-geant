"""Unit tests for platform survey adapters.

Covers:
- SurveyAdapter base class contract
- LimeSurveyAdapter: import, export, round-trip, submit, edge cases
- QualtricsAdapter: import, export, round-trip, submit, edge cases
- QTIAdapter: import, export, round-trip, edge cases
- SurveyMonkeyAdapter: import, export, round-trip, edge cases
- Adapter registry (get_adapter)
- Capability discovery
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from m_shared.adapters import (
    LimeSurveyAdapter,
    QTIAdapter,
    QualtricsAdapter,
    SurveyAdapter,
    SurveyMonkeyAdapter,
    get_adapter,
)
from m_shared.models import AnswerOption, Question, QuestionType, Response, Section, Survey

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MINIMAL_LSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>42</sid>
    <surveyls_title>Minimal Survey</surveyls_title>
    <surveyls_description>Test description</surveyls_description>
  </row></rows></surveys>
  <groups><rows>
    <row>
      <gid>1</gid><group_name>Group One</group_name>
      <description>First group</description><group_order>1</group_order>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>10</qid><gid>1</gid><type>L</type>
      <question>Pick one</question><mandatory>Y</mandatory>
      <question_order>1</question_order><parent_qid>0</parent_qid>
    </row>
    <row>
      <qid>11</qid><gid>1</gid><type>T</type>
      <question>Any comments?</question><mandatory>N</mandatory>
      <question_order>2</question_order><parent_qid>0</parent_qid>
    </row>
  </rows></questions>
  <answers><rows>
    <row><qid>10</qid><code>A1</code><answer>Option A</answer><sortorder>1</sortorder></row>
    <row><qid>10</qid><code>A2</code><answer>Option B</answer><sortorder>2</sortorder></row>
  </rows></answers>
</document>
"""

MULTI_SECTION_LSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>99</sid>
    <surveyls_title>Multi-Section</surveyls_title>
    <surveyls_description></surveyls_description>
  </row></rows></surveys>
  <groups><rows>
    <row><gid>1</gid><group_name>Section A</group_name><description></description><group_order>1</group_order></row>
    <row><gid>2</gid><group_name>Section B</group_name><description></description><group_order>2</group_order></row>
  </rows></groups>
  <questions><rows>
    <row><qid>1</qid><gid>1</gid><type>T</type><question>Q1</question><mandatory>N</mandatory><question_order>1</question_order><parent_qid>0</parent_qid></row>
    <row><qid>2</qid><gid>2</gid><type>M</type><question>Q2</question><mandatory>Y</mandatory><question_order>1</question_order><parent_qid>0</parent_qid></row>
  </rows></questions>
  <answers><rows>
    <row><qid>2</qid><code>X</code><answer>Choice X</answer><sortorder>1</sortorder></row>
    <row><qid>2</qid><code>Y</code><answer>Choice Y</answer><sortorder>2</sortorder></row>
  </rows></answers>
</document>
"""


def make_minimal_qsf(survey_id="SV_test", blocks=None, questions=None):
    """Build a minimal QSF dict and return it as a JSON string."""
    blocks = blocks or [
        {
            "Type": "Default",
            "Description": "Block One",
            "ID": "BL_1",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID1"}],
        }
    ]
    questions = questions or [
        {
            "Element": "SQ",
            "Payload": {
                "QuestionID": "QID1",
                "QuestionText": "How satisfied are you?",
                "QuestionType": "MC",
                "Selector": "SAVR",
                "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                "ChoiceOrder": ["1", "2"],
                "Validation": {"Settings": {"ForceResponse": "ON"}},
            },
        }
    ]
    return json.dumps(
        {
            "SurveyEntry": {
                "SurveyID": survey_id,
                "SurveyName": "Test Survey",
                "SurveyDescription": "A test",
            },
            "SurveyElements": [
                {
                    "Element": "FL",
                    "Payload": {
                        "Flow": [{"Type": "Block", "ID": "BL_1", "FlowID": "FL_1"}],
                        "FlowID": "FL_root",
                        "Type": "Root",
                    },
                },
                {"Element": "BL", "Payload": blocks},
                *questions,
            ],
        }
    )


def make_internal_survey() -> Survey:
    """Return a simple internal Survey for export tests."""
    return Survey(
        id="survey_export_test",
        title="Export Test Survey",
        description="Testing export",
        sections=[
            Section(
                id="sec_1",
                title="General",
                description="",
                order=0,
                questions=[
                    Question(
                        id="q_1",
                        text="Favourite colour?",
                        type=QuestionType.SINGLE_CHOICE,
                        required=True,
                        answer_options=[
                            AnswerOption(id="opt_red", text="Red", value="red"),
                            AnswerOption(id="opt_blue", text="Blue", value="blue"),
                        ],
                        min_value=None,
                        max_value=None,
                        step=None,
                    ),
                    Question(
                        id="q_2",
                        text="Tell us more",
                        type=QuestionType.OPEN_ENDED,
                        required=False,
                        min_value=None,
                        max_value=None,
                        step=None,
                    ),
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# SurveyAdapter base class
# ---------------------------------------------------------------------------


class TestSurveyAdapterBase:
    """SurveyAdapter enforces the abstract interface and default submit behaviour."""

    def test_cannot_instantiate_directly(self):
        """SurveyAdapter is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            SurveyAdapter()

    def test_submit_responses_raises_not_implemented(self):
        """Default submit_responses raises NotImplementedError."""

        class MinimalAdapter(SurveyAdapter):
            def import_survey(self, raw):
                return Survey(id="x", title="x", sections=[])

            def export_survey(self, survey):
                return ""

            def capabilities(self):
                return {"import", "export"}

        adapter = MinimalAdapter()
        with pytest.raises(NotImplementedError):
            adapter.submit_responses("sid", [])

    def test_not_implemented_message_contains_class_name(self):
        """NotImplementedError message names the concrete class."""

        class MyAdapter(SurveyAdapter):
            def import_survey(self, raw):
                return Survey(id="x", title="x", sections=[])

            def export_survey(self, survey):
                return ""

            def capabilities(self):
                return {"import", "export"}

        with pytest.raises(NotImplementedError, match="MyAdapter"):
            MyAdapter().submit_responses("sid", [])


# ---------------------------------------------------------------------------
# LimeSurveyAdapter — import
# ---------------------------------------------------------------------------


class TestLimeSurveyAdapterImport:
    """LimeSurveyAdapter.import_survey parses LSS XML correctly."""

    def setup_method(self):
        self.adapter = LimeSurveyAdapter()

    def test_survey_metadata(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        assert survey.title == "Minimal Survey"
        assert survey.description == "Test description"
        assert survey.id == "42"
        assert survey.metadata["platform"] == "limesurvey"

    def test_section_count_and_title(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        assert len(survey.sections) == 1
        assert survey.sections[0].title == "Group One"

    def test_question_types_mapped(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        questions = survey.sections[0].questions
        assert len(questions) == 2
        assert questions[0].type == QuestionType.SINGLE_CHOICE
        assert questions[1].type == QuestionType.OPEN_ENDED

    def test_required_flag(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        assert survey.sections[0].questions[0].required is True
        assert survey.sections[0].questions[1].required is False

    def test_answer_options_parsed(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        opts = survey.sections[0].questions[0].answer_options
        assert len(opts) == 2
        assert opts[0].text == "Option A"
        assert opts[0].value == "A1"
        assert opts[1].text == "Option B"

    def test_answer_options_preserve_ls_code(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        opt = survey.sections[0].questions[0].answer_options[0]
        assert opt.metadata["ls_code"] == "A1"

    def test_multiple_sections_ordered(self):
        survey = self.adapter.import_survey(MULTI_SECTION_LSS)
        assert len(survey.sections) == 2
        assert survey.sections[0].title == "Section A"
        assert survey.sections[1].title == "Section B"

    def test_multiple_choice_question_type(self):
        survey = self.adapter.import_survey(MULTI_SECTION_LSS)
        q = survey.sections[1].questions[0]
        assert q.type == QuestionType.MULTIPLE_CHOICE

    def test_subquestions_skipped(self):
        """Questions with non-zero parent_qid are sub-questions and must be skipped."""
        lss = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>1</sid><surveyls_title>T</surveyls_title><surveyls_description></surveyls_description>
  </row></rows></surveys>
  <groups><rows>
    <row><gid>1</gid><group_name>G</group_name><description></description><group_order>1</group_order></row>
  </rows></groups>
  <questions><rows>
    <row><qid>10</qid><gid>1</gid><type>L</type><question>Parent</question>
         <mandatory>Y</mandatory><question_order>1</question_order><parent_qid>0</parent_qid></row>
    <row><qid>11</qid><gid>1</gid><type>T</type><question>Sub-question</question>
         <mandatory>N</mandatory><question_order>2</question_order><parent_qid>10</parent_qid></row>
  </rows></questions>
  <answers><rows>
    <row><qid>10</qid><code>A1</code><answer>Yes</answer><sortorder>1</sortorder></row>
  </rows></answers>
</document>
"""
        survey = self.adapter.import_survey(lss)
        # qid=11 has parent_qid=10 → sub-question, must be excluded
        assert len(survey.sections[0].questions) == 1
        assert survey.sections[0].questions[0].text == "Parent"

    def test_invalid_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid LSS XML"):
            self.adapter.import_survey("not xml at all <<<")

    def test_missing_surveys_section_raises_value_error(self):
        with pytest.raises(ValueError, match="missing"):
            self.adapter.import_survey("<document><groups/></document>")

    def test_unknown_question_type_skipped(self):
        """Unrecognised LS type codes are skipped with a warning, not an error."""
        lss = MINIMAL_LSS.replace("<type>T</type>", "<type>UNKNOWN_TYPE</type>")
        survey = self.adapter.import_survey(lss)
        types = [q.type for s in survey.sections for q in s.questions]
        assert QuestionType.OPEN_ENDED not in types

    def test_slider_question_has_bounds(self):
        lss = MINIMAL_LSS.replace("<type>T</type>", "<type>N</type>")
        survey = self.adapter.import_survey(lss)
        slider_qs = [
            q for s in survey.sections for q in s.questions if q.type == QuestionType.SLIDER
        ]
        assert slider_qs, "Expected at least one slider question"
        q = slider_qs[0]
        assert q.min_value is not None
        assert q.max_value is not None
        assert q.step is not None


# ---------------------------------------------------------------------------
# LimeSurveyAdapter — export
# ---------------------------------------------------------------------------


class TestLimeSurveyAdapterExport:
    """LimeSurveyAdapter.export_survey serialises to valid LSS XML."""

    def setup_method(self):
        self.adapter = LimeSurveyAdapter()

    def test_export_produces_xml_string(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert isinstance(exported, str)
        assert "<document>" in exported

    def test_export_contains_survey_title(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "Export Test Survey" in exported

    def test_export_contains_question_text(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "Favourite colour?" in exported
        assert "Tell us more" in exported

    def test_export_contains_answer_options(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "Red" in exported
        assert "Blue" in exported

    def test_export_mandatory_flag(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "<mandatory>Y</mandatory>" in exported
        assert "<mandatory>N</mandatory>" in exported


# ---------------------------------------------------------------------------
# LimeSurveyAdapter — round-trip
# ---------------------------------------------------------------------------


class TestLimeSurveyAdapterRoundTrip:
    """Import → export → re-import preserves survey structure."""

    def setup_method(self):
        self.adapter = LimeSurveyAdapter()

    def test_title_preserved(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        assert survey.title == survey2.title

    def test_section_count_preserved(self):
        survey = self.adapter.import_survey(MULTI_SECTION_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        assert len(survey.sections) == len(survey2.sections)

    def test_question_texts_preserved(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        orig = [q.text for s in survey.sections for q in s.questions]
        rt = [q.text for s in survey2.sections for q in s.questions]
        assert orig == rt

    def test_answer_options_preserved(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        orig = [o.text for s in survey.sections for q in s.questions for o in q.answer_options]
        rt = [o.text for s in survey2.sections for q in s.questions for o in q.answer_options]
        assert orig == rt

    def test_question_types_preserved(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        orig = [q.type for s in survey.sections for q in s.questions]
        rt = [q.type for s in survey2.sections for q in s.questions]
        assert orig == rt

    def test_question_order_imported(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        questions = survey.sections[0].questions
        assert questions[0].order == 1
        assert questions[1].order == 2

    def test_question_order_preserved_on_round_trip(self):
        survey = self.adapter.import_survey(MINIMAL_LSS)
        survey2 = self.adapter.import_survey(self.adapter.export_survey(survey))
        orders1 = [q.order for s in survey.sections for q in s.questions]
        orders2 = [q.order for s in survey2.sections for q in s.questions]
        assert orders1 == orders2


# ---------------------------------------------------------------------------
# LimeSurveyAdapter — submit
# ---------------------------------------------------------------------------


class TestLimeSurveyAdapterSubmit:
    """LimeSurveyAdapter.submit_responses calls the RemoteControl 2 API correctly."""

    def test_submit_raises_without_credentials(self):
        adapter = LimeSurveyAdapter()
        with pytest.raises(ValueError, match="API URL"):
            adapter.submit_responses("42", [])

    def test_submit_calls_get_session_key(self):
        adapter = LimeSurveyAdapter(
            api_url="https://survey.example.com/rc",
            username="admin",
            password="secret",
        )
        responses = [
            Response(id="r1", question_id="10", answer_value="A1", metadata={"ls_qid": "10"})
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        # get_session_key → "sess_key", list_questions → [...], add_response → 1, release → "OK"
        mock_resp.json.side_effect = [
            {"result": "sess_key", "error": None, "id": 1},
            {"result": [{"id": "10", "gid": "5"}], "error": None, "id": 1},
            {"result": 1, "error": None, "id": 1},
            {"result": "OK", "error": None, "id": 1},
        ]

        with patch(
            "m_shared.adapters.limesurvey.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.submit_responses("42", responses)

        assert mock_post.call_count == 4
        # First call must be get_session_key
        first_payload = json.loads(mock_post.call_args_list[0].kwargs["data"])
        assert first_payload["method"] == "get_session_key"
        # Second call must be list_questions
        second_payload = json.loads(mock_post.call_args_list[1].kwargs["data"])
        assert second_payload["method"] == "list_questions"
        # Third call must be add_response
        third_payload = json.loads(mock_post.call_args_list[2].kwargs["data"])
        assert third_payload["method"] == "add_response"
        # Verify SGQA key in the add_response payload
        response_data = third_payload["params"][2]
        assert "42X5X10" in response_data

    def test_submit_releases_session_on_api_error(self):
        """Session key is released even when add_response returns an error."""
        adapter = LimeSurveyAdapter(
            api_url="https://survey.example.com/rc",
            username="admin",
            password="secret",
        )

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        # get_session_key → "sess_key", list_questions → [], add_response → error, release → "OK"
        mock_resp.json.side_effect = [
            {"result": "sess_key", "error": None, "id": 1},
            {"result": [], "error": None, "id": 1},
            {"result": {"status": "Error: survey is not active"}, "error": None, "id": 1},
            {"result": "OK", "error": None, "id": 1},
        ]

        with patch("m_shared.adapters.limesurvey.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="add_response failed"):
                adapter.submit_responses("42", [])

        # release_session_key should still have been called (4 total posts)
        assert mock_resp.json.call_count == 4

    def test_multiple_choice_response_serialised_as_flags(self):
        """Multiple choice answers produce per-option SGQA flag entries."""
        from m_shared.adapters.limesurvey import _responses_to_ls_format

        resp = Response(
            id="r1",
            question_id="20",
            answer_value=["X", "Y"],
            metadata={"ls_qid": "20"},
        )
        data = _responses_to_ls_format([resp], "42", {"20": "100"})
        assert data["42X100X20[X]"] == "Y"
        assert data["42X100X20[Y]"] == "Y"

    def test_open_ended_response_serialised_as_string(self):
        from m_shared.adapters.limesurvey import _responses_to_ls_format

        resp = Response(
            id="r2",
            question_id="11",
            answer_value="Some free text",
            metadata={"ls_qid": "11"},
        )
        data = _responses_to_ls_format([resp], "42", {"11": "100"})
        assert data["42X100X11"] == "Some free text"

    def test_sgqa_key_format(self):
        """SGQA keys follow <sid>X<gid>X<qid> format."""
        from m_shared.adapters.limesurvey import _responses_to_ls_format

        resp = Response(
            id="r3",
            question_id="q_200",
            answer_value="Yes",
            metadata={"ls_qid": "200"},
        )
        data = _responses_to_ls_format([resp], "12345", {"200": "50"})
        assert "12345X50X200" in data
        assert data["12345X50X200"] == "Yes"

    def test_missing_gid_raises_value_error(self):
        """Raises ValueError when ls_qid is not found in gid_map."""
        from m_shared.adapters.limesurvey import _responses_to_ls_format

        resp = Response(
            id="r4",
            question_id="q_999",
            answer_value="Yes",
            metadata={"ls_qid": "999"},
        )
        with pytest.raises(ValueError, match="999"):
            _responses_to_ls_format([resp], "42", {})  # empty gid_map


# ---------------------------------------------------------------------------
# QualtricsAdapter — import
# ---------------------------------------------------------------------------


class TestQualtricsAdapterImport:
    """QualtricsAdapter.import_survey parses QSF JSON correctly."""

    def setup_method(self):
        self.adapter = QualtricsAdapter()

    def test_survey_metadata(self):
        survey = self.adapter.import_survey(make_minimal_qsf())
        assert survey.title == "Test Survey"
        assert survey.description == "A test"
        assert survey.id == "SV_test"
        assert survey.metadata["platform"] == "qualtrics"

    def test_section_from_block(self):
        survey = self.adapter.import_survey(make_minimal_qsf())
        assert len(survey.sections) == 1
        assert survey.sections[0].title == "Block One"

    def test_single_choice_mc(self):
        survey = self.adapter.import_survey(make_minimal_qsf())
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.SINGLE_CHOICE
        assert q.required is True

    def test_multiple_choice_mc(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Pick all",
                    "QuestionType": "MC",
                    "Selector": "MAVR",
                    "Choices": {"1": {"Display": "A"}, "2": {"Display": "B"}},
                    "ChoiceOrder": ["1", "2"],
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        assert survey.sections[0].questions[0].type == QuestionType.MULTIPLE_CHOICE

    def test_text_entry_is_open_ended(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Describe",
                    "QuestionType": "TE",
                    "Selector": "ML",
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        assert survey.sections[0].questions[0].type == QuestionType.OPEN_ENDED

    def test_slider_question(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Rate 0-10",
                    "QuestionType": "Slider",
                    "Selector": "HSLIDER",
                    "Configuration": {"CSSliderMin": 0, "CSSliderMax": 10, "GridLines": 10},
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.SLIDER
        assert q.min_value == 0.0
        assert q.max_value == 10.0
        assert q.step is not None

    def test_rank_order_question(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Rank these",
                    "QuestionType": "RO",
                    "Selector": "Rank",
                    "Choices": {"1": {"Display": "A"}, "2": {"Display": "B"}},
                    "ChoiceOrder": ["1", "2"],
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        assert survey.sections[0].questions[0].type == QuestionType.RANKING

    def test_answer_options_in_order(self):
        survey = self.adapter.import_survey(make_minimal_qsf())
        opts = survey.sections[0].questions[0].answer_options
        assert [o.text for o in opts] == ["Yes", "No"]

    def test_flow_determines_section_order(self):
        """Blocks appear in flow order, not declaration order."""
        qsf = json.dumps(
            {
                "SurveyEntry": {
                    "SurveyID": "SV_x",
                    "SurveyName": "Flow Test",
                    "SurveyDescription": "",
                },
                "SurveyElements": [
                    {
                        "Element": "FL",
                        "Payload": {
                            "Flow": [
                                {"Type": "Block", "ID": "BL_2", "FlowID": "FL_1"},
                                {"Type": "Block", "ID": "BL_1", "FlowID": "FL_2"},
                            ],
                            "FlowID": "FL_root",
                            "Type": "Root",
                        },
                    },
                    {
                        "Element": "BL",
                        "Payload": [
                            {
                                "Type": "Default",
                                "Description": "First Declared",
                                "ID": "BL_1",
                                "BlockElements": [],
                            },
                            {
                                "Type": "Default",
                                "Description": "Second Declared",
                                "ID": "BL_2",
                                "BlockElements": [],
                            },
                        ],
                    },
                ],
            }
        )
        survey = self.adapter.import_survey(qsf)
        assert survey.sections[0].title == "Second Declared"
        assert survey.sections[1].title == "First Declared"

    def test_html_stripped_from_question_text(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "<strong>Bold question</strong>",
                    "QuestionType": "TE",
                    "Selector": "SL",
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        assert survey.sections[0].questions[0].text == "Bold question"

    def test_trash_block_excluded(self):
        """BL blocks with Type=Trash must not appear as sections."""
        qsf = json.dumps(
            {
                "SurveyEntry": {
                    "SurveyID": "SV_x",
                    "SurveyName": "Trash Test",
                    "SurveyDescription": "",
                },
                "SurveyElements": [
                    {"Element": "FL", "Payload": {"Flow": [], "FlowID": "FL_root", "Type": "Root"}},
                    {
                        "Element": "BL",
                        "Payload": [
                            {
                                "Type": "Default",
                                "Description": "Real Block",
                                "ID": "BL_1",
                                "BlockElements": [],
                            },
                            {
                                "Type": "Trash",
                                "Description": "Trash",
                                "ID": "BL_trash",
                                "BlockElements": [],
                            },
                        ],
                    },
                ],
            }
        )
        survey = self.adapter.import_survey(qsf)
        section_titles = [s.title for s in survey.sections]
        assert "Trash" not in section_titles

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid QSF JSON"):
            self.adapter.import_survey("{not valid json")

    def test_unknown_question_type_skipped(self):
        qs = [
            {
                "Element": "SQ",
                "Payload": {
                    "QuestionID": "QID1",
                    "QuestionText": "Exotic question",
                    "QuestionType": "EXOTIC",
                    "Selector": "???",
                    "Validation": {"Settings": {"ForceResponse": "OFF"}},
                },
            }
        ]
        survey = self.adapter.import_survey(make_minimal_qsf(questions=qs))
        assert survey.sections[0].questions == []

    def test_block_referencing_unknown_qid_skipped(self):
        """Block referencing a QID with no matching SQ element is silently skipped."""
        qsf = json.dumps(
            {
                "SurveyEntry": {
                    "SurveyID": "SV_x",
                    "SurveyName": "Missing QID",
                    "SurveyDescription": "",
                },
                "SurveyElements": [
                    {
                        "Element": "FL",
                        "Payload": {
                            "Flow": [{"Type": "Block", "ID": "BL_1"}],
                            "FlowID": "FL_root",
                            "Type": "Root",
                        },
                    },
                    {
                        "Element": "BL",
                        "Payload": [
                            {
                                "Type": "Default",
                                "Description": "B",
                                "ID": "BL_1",
                                "BlockElements": [
                                    {"Type": "Question", "QuestionID": "QID_MISSING"}
                                ],
                            }
                        ],
                    },
                ],
            }
        )
        survey = self.adapter.import_survey(qsf)
        assert survey.sections[0].questions == []


# ---------------------------------------------------------------------------
# QualtricsAdapter — export
# ---------------------------------------------------------------------------


class TestQualtricsAdapterExport:
    """QualtricsAdapter.export_survey serialises to valid QSF JSON."""

    def setup_method(self):
        self.adapter = QualtricsAdapter()

    def test_export_produces_json_string(self):
        exported = self.adapter.export_survey(make_internal_survey())
        parsed = json.loads(exported)  # must not raise
        assert "SurveyEntry" in parsed
        assert "SurveyElements" in parsed

    def test_export_survey_name(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        assert parsed["SurveyEntry"]["SurveyName"] == "Export Test Survey"

    def test_export_contains_sq_elements(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        sq_elements = [el for el in parsed["SurveyElements"] if el["Element"] == "SQ"]
        assert len(sq_elements) == 2

    def test_export_contains_bl_element(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        bl = [el for el in parsed["SurveyElements"] if el["Element"] == "BL"]
        assert len(bl) == 1

    def test_export_contains_fl_element(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        fl = [el for el in parsed["SurveyElements"] if el["Element"] == "FL"]
        assert len(fl) == 1

    def test_export_answer_choices_present(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "Red" in exported
        assert "Blue" in exported


# ---------------------------------------------------------------------------
# QualtricsAdapter — round-trip
# ---------------------------------------------------------------------------


class TestQualtricsAdapterRoundTrip:
    """Import → export → re-import preserves survey structure."""

    def setup_method(self):
        self.adapter = QualtricsAdapter()

    def _full_qsf(self):
        return make_minimal_qsf(
            questions=[
                {
                    "Element": "SQ",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionText": "Single choice",
                        "QuestionType": "MC",
                        "Selector": "SAVR",
                        "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                        "ChoiceOrder": ["1", "2"],
                        "Validation": {"Settings": {"ForceResponse": "ON"}},
                    },
                },
                {
                    "Element": "SQ",
                    "Payload": {
                        "QuestionID": "QID2",
                        "QuestionText": "Open text",
                        "QuestionType": "TE",
                        "Selector": "ML",
                        "Validation": {"Settings": {"ForceResponse": "OFF"}},
                    },
                },
            ]
        )

    def test_title_preserved(self):
        s1 = self.adapter.import_survey(self._full_qsf())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert s1.title == s2.title

    def test_question_count_preserved(self):
        s1 = self.adapter.import_survey(self._full_qsf())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert sum(len(s.questions) for s in s1.sections) == sum(
            len(s.questions) for s in s2.sections
        )

    def test_question_types_preserved(self):
        s1 = self.adapter.import_survey(self._full_qsf())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        t1 = [q.type for s in s1.sections for q in s.questions]
        t2 = [q.type for s in s2.sections for q in s.questions]
        assert t1 == t2

    def test_answer_options_preserved(self):
        s1 = self.adapter.import_survey(self._full_qsf())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        o1 = [o.text for s in s1.sections for q in s.questions for o in q.answer_options]
        o2 = [o.text for s in s2.sections for q in s.questions for o in q.answer_options]
        assert o1 == o2


# ---------------------------------------------------------------------------
# QualtricsAdapter — submit
# ---------------------------------------------------------------------------


class TestQualtricsAdapterSubmit:
    """QualtricsAdapter.submit_responses calls the Response Import API correctly."""

    def test_submit_raises_without_credentials(self):
        with pytest.raises(ValueError, match="api_token"):
            QualtricsAdapter().submit_responses("SV_test", [])

    def test_submit_raises_without_datacenter(self):
        with pytest.raises(ValueError):
            QualtricsAdapter(api_token="tok").submit_responses("SV_test", [])

    def test_submit_posts_to_correct_url(self):
        adapter = QualtricsAdapter(api_token="tok123", datacenter_id="iad1")
        responses = [
            Response(id="r1", question_id="QID1", answer_value="1", metadata={"qsf_qid": "QID1"})
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"meta": {"httpStatus": "200 - OK"}}

        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.submit_responses("SV_abc", responses)

        url = mock_post.call_args.args[0]
        assert "iad1.qualtrics.com" in url
        assert "SV_abc" in url

    def test_submit_sets_api_token_header(self):
        adapter = QualtricsAdapter(api_token="my-secret-token", datacenter_id="iad1")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"meta": {"httpStatus": "200 - OK"}}

        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.submit_responses("SV_abc", [])

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-API-TOKEN"] == "my-secret-token"

    def test_submit_serialises_responses_in_body(self):
        adapter = QualtricsAdapter(api_token="tok", datacenter_id="iad1")
        responses = [
            Response(id="r1", question_id="QID1", answer_value="2", metadata={"qsf_qid": "QID1"}),
            Response(
                id="r2", question_id="QID2", answer_value=["A", "C"], metadata={"qsf_qid": "QID2"}
            ),
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"meta": {"httpStatus": "200 - OK"}}

        with patch(
            "m_shared.adapters.qualtrics.requests.post", return_value=mock_resp
        ) as mock_post:
            adapter.submit_responses("SV_abc", responses)

        body = mock_post.call_args.kwargs["json"]
        assert body["values"]["QID1"] == "2"
        assert body["values"]["QID2"] == ["A", "C"]

    def test_submit_raises_on_api_error_status(self):
        adapter = QualtricsAdapter(api_token="tok", datacenter_id="iad1")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"meta": {"httpStatus": "400 - Bad Request"}}

        with patch("m_shared.adapters.qualtrics.requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Qualtrics API error"):
                adapter.submit_responses("SV_abc", [])

    def test_submit_raises_on_network_error(self):
        import requests as req_lib

        adapter = QualtricsAdapter(api_token="tok", datacenter_id="iad1")

        with patch(
            "m_shared.adapters.qualtrics.requests.post",
            side_effect=req_lib.ConnectionError("timeout"),
        ):
            with pytest.raises(RuntimeError, match="Qualtrics response import failed"):
                adapter.submit_responses("SV_abc", [])


# ---------------------------------------------------------------------------
# QTI shared fixtures
# ---------------------------------------------------------------------------

MINIMAL_QTI = """\
<?xml version="1.0"?>
<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0"
                identifier="survey_qti" title="QTI Test Survey">
  <testPart identifier="part1" navigationMode="linear" submissionMode="individual">
    <assessmentSection identifier="sec1" title="General" visible="true">
      <assessmentItem identifier="q1" title="Pick one" adaptive="false" timeDependent="false">
        <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier"/>
        <itemBody>
          <choiceInteraction responseIdentifier="RESPONSE" shuffle="false" maxChoices="1">
            <prompt>Pick one option</prompt>
            <simpleChoice identifier="A">Option A</simpleChoice>
            <simpleChoice identifier="B">Option B</simpleChoice>
          </choiceInteraction>
        </itemBody>
      </assessmentItem>
      <assessmentItem identifier="q2" title="Free text" adaptive="false" timeDependent="false">
        <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="string"/>
        <itemBody>
          <extendedTextInteraction responseIdentifier="RESPONSE" shuffle="false">
            <prompt>Describe your approach</prompt>
          </extendedTextInteraction>
        </itemBody>
      </assessmentItem>
    </assessmentSection>
  </testPart>
</assessmentTest>
"""

MULTI_SECTION_QTI = """\
<?xml version="1.0"?>
<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0"
                identifier="survey_multi" title="Multi-Section QTI">
  <testPart identifier="part1" navigationMode="linear" submissionMode="individual">
    <assessmentSection identifier="sec1" title="Section One" visible="true">
      <assessmentItem identifier="q1" title="Q1" adaptive="false" timeDependent="false">
        <responseDeclaration identifier="RESPONSE" cardinality="multiple" baseType="identifier"/>
        <itemBody>
          <choiceInteraction responseIdentifier="RESPONSE" shuffle="false" maxChoices="0">
            <prompt>Pick all that apply</prompt>
            <simpleChoice identifier="X">Choice X</simpleChoice>
            <simpleChoice identifier="Y">Choice Y</simpleChoice>
          </choiceInteraction>
        </itemBody>
      </assessmentItem>
    </assessmentSection>
    <assessmentSection identifier="sec2" title="Section Two" visible="true">
      <assessmentItem identifier="q2" title="Slider" adaptive="false" timeDependent="false">
        <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="float"/>
        <itemBody>
          <sliderInteraction responseIdentifier="RESPONSE" shuffle="false"
                             lowerBound="0" upperBound="10" step="1">
            <prompt>Rate from 0 to 10</prompt>
          </sliderInteraction>
        </itemBody>
      </assessmentItem>
    </assessmentSection>
  </testPart>
</assessmentTest>
"""


# ---------------------------------------------------------------------------
# QTIAdapter — import
# ---------------------------------------------------------------------------


class TestQTIAdapterImport:
    """QTIAdapter.import_survey parses QTI 3.0 XML correctly."""

    def setup_method(self):
        self.adapter = QTIAdapter()

    def test_survey_metadata(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        assert survey.title == "QTI Test Survey"
        assert survey.id == "survey_qti"
        assert survey.metadata["platform"] == "qti"

    def test_section_parsed(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        assert len(survey.sections) == 1
        assert survey.sections[0].title == "General"

    def test_single_choice_question(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.SINGLE_CHOICE
        assert q.text == "Pick one option"

    def test_open_ended_question(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        q = survey.sections[0].questions[1]
        assert q.type == QuestionType.OPEN_ENDED
        assert q.text == "Describe your approach"

    def test_answer_options_from_simple_choices(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        opts = survey.sections[0].questions[0].answer_options
        assert len(opts) == 2
        assert opts[0].text == "Option A"
        assert opts[0].value == "A"
        assert opts[1].text == "Option B"

    def test_multiple_choice_from_cardinality(self):
        """cardinality=multiple on responseDeclaration maps to multiple_choice."""
        survey = self.adapter.import_survey(MULTI_SECTION_QTI)
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.MULTIPLE_CHOICE

    def test_slider_with_bounds(self):
        survey = self.adapter.import_survey(MULTI_SECTION_QTI)
        q = survey.sections[1].questions[0]
        assert q.type == QuestionType.SLIDER
        assert q.min_value == 0.0
        assert q.max_value == 10.0
        assert q.step == 1.0

    def test_multiple_sections_from_multiple_assessment_sections(self):
        survey = self.adapter.import_survey(MULTI_SECTION_QTI)
        assert len(survey.sections) == 2
        assert survey.sections[0].title == "Section One"
        assert survey.sections[1].title == "Section Two"

    def test_section_order_reflects_xml_order(self):
        survey = self.adapter.import_survey(MULTI_SECTION_QTI)
        assert survey.sections[0].order == 0
        assert survey.sections[1].order == 1

    def test_qti_identifier_preserved_in_metadata(self):
        survey = self.adapter.import_survey(MINIMAL_QTI)
        q = survey.sections[0].questions[0]
        assert q.metadata["qti_identifier"] == "q1"

    def test_invalid_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid QTI XML"):
            self.adapter.import_survey("<<< not xml")

    def test_wrong_root_element_raises_value_error(self):
        with pytest.raises(ValueError, match="assessmentTest"):
            self.adapter.import_survey("<document><something/></document>")

    def test_item_without_item_body_skipped(self):
        qti = """\
<?xml version="1.0"?>
<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0"
                identifier="x" title="T">
  <testPart identifier="p1" navigationMode="linear" submissionMode="individual">
    <assessmentSection identifier="s1" title="S" visible="true">
      <assessmentItem identifier="bad" title="No body" adaptive="false" timeDependent="false"/>
    </assessmentSection>
  </testPart>
</assessmentTest>"""
        survey = self.adapter.import_survey(qti)
        assert survey.sections[0].questions == []

    def test_item_without_known_interaction_skipped(self):
        qti = """\
<?xml version="1.0"?>
<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0"
                identifier="x" title="T">
  <testPart identifier="p1" navigationMode="linear" submissionMode="individual">
    <assessmentSection identifier="s1" title="S" visible="true">
      <assessmentItem identifier="exotic" title="Exotic" adaptive="false" timeDependent="false">
        <itemBody>
          <hotspotInteraction responseIdentifier="RESPONSE"/>
        </itemBody>
      </assessmentItem>
    </assessmentSection>
  </testPart>
</assessmentTest>"""
        survey = self.adapter.import_survey(qti)
        assert survey.sections[0].questions == []


# ---------------------------------------------------------------------------
# QTIAdapter — export
# ---------------------------------------------------------------------------


class TestQTIAdapterExport:
    """QTIAdapter.export_survey serialises to valid QTI 3.0 XML."""

    def setup_method(self):
        self.adapter = QTIAdapter()

    def test_export_produces_xml_string(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert isinstance(exported, str)
        assert "assessmentTest" in exported

    def test_export_survey_title_in_root(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert 'title="Export Test Survey"' in exported

    def test_export_contains_assessment_section(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "assessmentSection" in exported

    def test_export_contains_assessment_item(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "assessmentItem" in exported

    def test_export_choice_interaction_for_single_choice(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "choiceInteraction" in exported

    def test_export_text_interaction_for_open_ended(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "extendedTextInteraction" in exported

    def test_export_answer_option_texts(self):
        exported = self.adapter.export_survey(make_internal_survey())
        assert "Red" in exported
        assert "Blue" in exported

    def test_export_slider_has_bounds(self):
        from m_shared.models import Question, QuestionType, Section, Survey

        survey = Survey(
            id="s1",
            title="T",
            sections=[
                Section(
                    id="sec1",
                    title="S",
                    questions=[
                        Question(
                            id="q1",
                            text="Rate it",
                            type=QuestionType.SLIDER,
                            min_value=1.0,
                            max_value=5.0,
                            step=1.0,
                        )
                    ],
                )
            ],
        )
        exported = self.adapter.export_survey(survey)
        assert 'lowerBound="1"' in exported
        assert 'upperBound="5"' in exported


# ---------------------------------------------------------------------------
# QTIAdapter — round-trip
# ---------------------------------------------------------------------------


class TestQTIAdapterRoundTrip:
    """Import → export → re-import preserves survey structure."""

    def setup_method(self):
        self.adapter = QTIAdapter()

    def test_title_preserved(self):
        s1 = self.adapter.import_survey(MINIMAL_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert s1.title == s2.title

    def test_section_count_preserved(self):
        s1 = self.adapter.import_survey(MULTI_SECTION_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert len(s1.sections) == len(s2.sections)

    def test_question_texts_preserved(self):
        s1 = self.adapter.import_survey(MINIMAL_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        t1 = [q.text for s in s1.sections for q in s.questions]
        t2 = [q.text for s in s2.sections for q in s.questions]
        assert t1 == t2

    def test_question_types_preserved(self):
        s1 = self.adapter.import_survey(MULTI_SECTION_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        t1 = [q.type for s in s1.sections for q in s.questions]
        t2 = [q.type for s in s2.sections for q in s.questions]
        assert t1 == t2

    def test_answer_option_texts_preserved(self):
        s1 = self.adapter.import_survey(MINIMAL_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        o1 = [o.text for s in s1.sections for q in s.questions for o in q.answer_options]
        o2 = [o.text for s in s2.sections for q in s.questions for o in q.answer_options]
        assert o1 == o2

    def test_slider_bounds_preserved(self):
        s1 = self.adapter.import_survey(MULTI_SECTION_QTI)
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        slider1 = next(q for s in s1.sections for q in s.questions if q.type == QuestionType.SLIDER)
        slider2 = next(q for s in s2.sections for q in s.questions if q.type == QuestionType.SLIDER)
        assert slider1.min_value == slider2.min_value
        assert slider1.max_value == slider2.max_value


# ---------------------------------------------------------------------------
# QTIAdapter — submit (not supported)
# ---------------------------------------------------------------------------


class TestQTIAdapterSubmit:
    def test_submit_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="QTIAdapter"):
            QTIAdapter().submit_responses("survey_1", [])

    def test_capabilities_excludes_submit(self):
        assert "submit" not in QTIAdapter().capabilities()


# ---------------------------------------------------------------------------
# SurveyMonkey shared fixtures
# ---------------------------------------------------------------------------


def make_sm_survey(**overrides) -> str:
    data = {
        "id": "sm_999",
        "title": "SM Test Survey",
        "description": "Testing SM adapter",
        "pages": [
            {
                "id": "p1",
                "title": "Page 1",
                "description": "",
                "position": 1,
                "questions": [
                    {
                        "id": "q1",
                        "heading": "Do you agree?",
                        "family": "single_choice",
                        "subtype": "vertical",
                        "position": 1,
                        "required": True,
                        "answers": {
                            "choices": [
                                {"id": "c1", "text": "Yes", "position": 1},
                                {"id": "c2", "text": "No", "position": 2},
                            ]
                        },
                    },
                    {
                        "id": "q2",
                        "heading": "Explain your answer",
                        "family": "open_ended",
                        "subtype": "essay",
                        "position": 2,
                        "required": False,
                        "answers": {},
                    },
                ],
            }
        ],
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# SurveyMonkeyAdapter — import
# ---------------------------------------------------------------------------


class TestSurveyMonkeyAdapterImport:
    """SurveyMonkeyAdapter.import_survey parses SM API JSON correctly."""

    def setup_method(self):
        self.adapter = SurveyMonkeyAdapter()

    def test_survey_metadata(self):
        survey = self.adapter.import_survey(make_sm_survey())
        assert survey.title == "SM Test Survey"
        assert survey.description == "Testing SM adapter"
        assert survey.id == "sm_999"
        assert survey.metadata["platform"] == "surveymonkey"

    def test_page_becomes_section(self):
        survey = self.adapter.import_survey(make_sm_survey())
        assert len(survey.sections) == 1
        assert survey.sections[0].title == "Page 1"

    def test_single_choice_question(self):
        survey = self.adapter.import_survey(make_sm_survey())
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.SINGLE_CHOICE
        assert q.required is True
        assert q.text == "Do you agree?"

    def test_open_ended_question(self):
        survey = self.adapter.import_survey(make_sm_survey())
        q = survey.sections[0].questions[1]
        assert q.type == QuestionType.OPEN_ENDED
        assert q.required is False

    def test_answer_options_parsed(self):
        survey = self.adapter.import_survey(make_sm_survey())
        opts = survey.sections[0].questions[0].answer_options
        assert [o.text for o in opts] == ["Yes", "No"]

    def test_multiple_choice_family(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Pick all",
                                "family": "multiple_choice",
                                "subtype": "vertical",
                                "position": 1,
                                "required": False,
                                "answers": {"choices": [{"id": "c1", "text": "A", "position": 1}]},
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        assert survey.sections[0].questions[0].type == QuestionType.MULTIPLE_CHOICE

    def test_ranking_family(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Rank",
                                "family": "ranking",
                                "subtype": "",
                                "position": 1,
                                "required": False,
                                "answers": {
                                    "choices": [
                                        {"id": "c1", "text": "First", "position": 1},
                                        {"id": "c2", "text": "Second", "position": 2},
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        assert survey.sections[0].questions[0].type == QuestionType.RANKING

    def test_slider_family(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Rate",
                                "family": "slider",
                                "subtype": "",
                                "position": 1,
                                "required": False,
                                "answers": {"ranges": [{"min": 0, "max": 100}]},
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        q = survey.sections[0].questions[0]
        assert q.type == QuestionType.SLIDER
        assert q.min_value == 0.0
        assert q.max_value == 100.0

    def test_matrix_expanded_to_row_questions(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Matrix",
                                "family": "matrix",
                                "subtype": "rating",
                                "position": 1,
                                "required": False,
                                "answers": {
                                    "rows": [
                                        {"id": "r1", "text": "Row A", "position": 1},
                                        {"id": "r2", "text": "Row B", "position": 2},
                                    ],
                                    "choices": [
                                        {"id": "c1", "text": "Agree", "position": 1},
                                        {"id": "c2", "text": "Disagree", "position": 2},
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        questions = survey.sections[0].questions
        assert len(questions) == 2
        assert questions[0].text == "Row A"
        assert questions[1].text == "Row B"
        assert all(q.type == QuestionType.SINGLE_CHOICE for q in questions)
        assert [o.text for o in questions[0].answer_options] == ["Agree", "Disagree"]

    def test_pages_sorted_by_position(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p2",
                        "title": "Second",
                        "description": "",
                        "position": 2,
                        "questions": [],
                    },
                    {
                        "id": "p1",
                        "title": "First",
                        "description": "",
                        "position": 1,
                        "questions": [],
                    },
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        assert survey.sections[0].title == "First"
        assert survey.sections[1].title == "Second"

    def test_unknown_family_skipped(self):
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Q",
                                "family": "imagepicker",
                                "subtype": "",
                                "position": 1,
                                "required": False,
                                "answers": {},
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        assert survey.sections[0].questions == []

    def test_presentation_family_skipped(self):
        """'presentation' questions are display-only and must be skipped."""
        sm = json.dumps(
            {
                "id": "x",
                "title": "T",
                "description": "",
                "pages": [
                    {
                        "id": "p1",
                        "title": "P",
                        "description": "",
                        "position": 1,
                        "questions": [
                            {
                                "id": "q1",
                                "heading": "Header text",
                                "family": "presentation",
                                "subtype": "",
                                "position": 1,
                                "required": False,
                                "answers": {},
                            }
                        ],
                    }
                ],
            }
        )
        survey = self.adapter.import_survey(sm)
        assert survey.sections[0].questions == []

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid SurveyMonkey JSON"):
            self.adapter.import_survey("{bad json")

    def test_sm_qid_preserved_in_metadata(self):
        survey = self.adapter.import_survey(make_sm_survey())
        q = survey.sections[0].questions[0]
        assert q.metadata["sm_qid"] == "q1"


# ---------------------------------------------------------------------------
# SurveyMonkeyAdapter — export
# ---------------------------------------------------------------------------


class TestSurveyMonkeyAdapterExport:
    """SurveyMonkeyAdapter.export_survey serialises to SM API JSON format."""

    def setup_method(self):
        self.adapter = SurveyMonkeyAdapter()

    def test_export_produces_valid_json(self):
        exported = self.adapter.export_survey(make_internal_survey())
        parsed = json.loads(exported)
        assert "id" in parsed
        assert "pages" in parsed

    def test_export_survey_title(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        assert parsed["title"] == "Export Test Survey"

    def test_export_section_becomes_page(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        assert len(parsed["pages"]) == 1
        assert parsed["pages"][0]["title"] == "General"

    def test_export_question_family(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        questions = parsed["pages"][0]["questions"]
        families = {q["family"] for q in questions}
        assert "single_choice" in families
        assert "open_ended" in families

    def test_export_choices_present(self):
        parsed = json.loads(self.adapter.export_survey(make_internal_survey()))
        choices_q = next(
            q for q in parsed["pages"][0]["questions"] if q.get("answers", {}).get("choices")
        )
        texts = [c["text"] for c in choices_q["answers"]["choices"]]
        assert "Red" in texts
        assert "Blue" in texts


# ---------------------------------------------------------------------------
# SurveyMonkeyAdapter — round-trip
# ---------------------------------------------------------------------------


class TestSurveyMonkeyAdapterRoundTrip:
    """Import → export → re-import preserves survey structure."""

    def setup_method(self):
        self.adapter = SurveyMonkeyAdapter()

    def test_title_preserved(self):
        s1 = self.adapter.import_survey(make_sm_survey())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert s1.title == s2.title

    def test_section_count_preserved(self):
        s1 = self.adapter.import_survey(make_sm_survey())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        assert len(s1.sections) == len(s2.sections)

    def test_question_types_preserved(self):
        s1 = self.adapter.import_survey(make_sm_survey())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        t1 = [q.type for s in s1.sections for q in s.questions]
        t2 = [q.type for s in s2.sections for q in s.questions]
        assert t1 == t2

    def test_question_texts_preserved(self):
        s1 = self.adapter.import_survey(make_sm_survey())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        tx1 = [q.text for s in s1.sections for q in s.questions]
        tx2 = [q.text for s in s2.sections for q in s.questions]
        assert tx1 == tx2

    def test_answer_options_preserved(self):
        s1 = self.adapter.import_survey(make_sm_survey())
        s2 = self.adapter.import_survey(self.adapter.export_survey(s1))
        o1 = [o.text for s in s1.sections for q in s.questions for o in q.answer_options]
        o2 = [o.text for s in s2.sections for q in s.questions for o in q.answer_options]
        assert o1 == o2

    def test_question_order_imported_from_position(self):
        survey = self.adapter.import_survey(make_sm_survey())
        questions = survey.sections[0].questions
        # SM positions are 1-based; stored as 0-based order
        assert questions[0].order == 0
        assert questions[1].order == 1


# ---------------------------------------------------------------------------
# SurveyMonkeyAdapter — submit (not supported)
# ---------------------------------------------------------------------------


class TestSurveyMonkeyAdapterSubmit:
    def test_submit_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="SurveyMonkeyAdapter"):
            SurveyMonkeyAdapter().submit_responses("sm_999", [])

    def test_capabilities_excludes_submit(self):
        assert "submit" not in SurveyMonkeyAdapter().capabilities()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    """get_adapter returns the correct adapter class for each format string."""

    def test_limesurvey_by_name(self):
        assert isinstance(get_adapter("limesurvey"), LimeSurveyAdapter)

    def test_lss_alias(self):
        assert isinstance(get_adapter("lss"), LimeSurveyAdapter)

    def test_qualtrics_by_name(self):
        assert isinstance(get_adapter("qualtrics"), QualtricsAdapter)

    def test_qsf_alias(self):
        assert isinstance(get_adapter("qsf"), QualtricsAdapter)

    def test_qti_by_name(self):
        assert isinstance(get_adapter("qti"), QTIAdapter)

    def test_surveymonkey_by_name(self):
        assert isinstance(get_adapter("surveymonkey"), SurveyMonkeyAdapter)

    def test_sm_alias(self):
        assert isinstance(get_adapter("sm"), SurveyMonkeyAdapter)

    def test_case_insensitive(self):
        assert isinstance(get_adapter("LimeSurvey"), LimeSurveyAdapter)
        assert isinstance(get_adapter("QUALTRICS"), QualtricsAdapter)
        assert isinstance(get_adapter("QTI"), QTIAdapter)
        assert isinstance(get_adapter("SurveyMonkey"), SurveyMonkeyAdapter)

    def test_unknown_format_raises_key_error(self):
        with pytest.raises(KeyError, match="No adapter for format"):
            get_adapter("surveyplanet")

    def test_kwargs_forwarded_to_adapter(self):
        adapter = get_adapter(
            "limesurvey", api_url="https://ls.example.com/rc", username="u", password="p"
        )
        assert adapter._api_url == "https://ls.example.com/rc"

    def test_qualtrics_kwargs_forwarded(self):
        adapter = get_adapter("qualtrics", api_token="tok", datacenter_id="fra1")
        assert adapter._api_token == "tok"
        assert adapter._datacenter_id == "fra1"


# ---------------------------------------------------------------------------
# Capability discovery
# ---------------------------------------------------------------------------


class TestCapabilityDiscovery:
    """capabilities() returns the correct sets for each adapter."""

    def test_limesurvey_supports_all(self):
        caps = LimeSurveyAdapter().capabilities()
        assert "import" in caps
        assert "export" in caps
        assert "submit" in caps

    def test_qualtrics_supports_all(self):
        caps = QualtricsAdapter().capabilities()
        assert "import" in caps
        assert "export" in caps
        assert "submit" in caps

    def test_qti_import_export_only(self):
        caps = QTIAdapter().capabilities()
        assert "import" in caps
        assert "export" in caps
        assert "submit" not in caps

    def test_surveymonkey_import_export_only(self):
        caps = SurveyMonkeyAdapter().capabilities()
        assert "import" in caps
        assert "export" in caps
        assert "submit" not in caps

    def test_capabilities_returns_set(self):
        for adapter in [
            LimeSurveyAdapter(),
            QualtricsAdapter(),
            QTIAdapter(),
            SurveyMonkeyAdapter(),
        ]:
            assert isinstance(adapter.capabilities(), set)


# ---------------------------------------------------------------------------
# Cross-platform integration: import from A → export to B → re-import from B
# ---------------------------------------------------------------------------


def _all_questions(survey):
    return [q for s in survey.sections for q in s.questions]


def _all_option_texts(survey):
    return [o.text for s in survey.sections for q in s.questions for o in q.answer_options]


class TestCrossPlatformRoundTrip:
    """Verify survey structure survives import from one platform and export to another.

    Each test follows the pattern:
        source_raw → adapter_A.import → Survey → adapter_B.export → raw_B
                   → adapter_B.import → Survey'
    And asserts that question count, types, texts, and answer options are preserved.
    Platform-specific metadata fields that have no equivalent in the target format
    are intentionally not checked — only the common-denominator fields.
    """

    # ------------------------------------------------------------------
    # LimeSurvey → Qualtrics
    # ------------------------------------------------------------------

    def test_limesurvey_to_qualtrics_question_count(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_limesurvey_to_qualtrics_question_types(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert [q.type for q in _all_questions(survey)] == [q.type for q in _all_questions(survey2)]

    def test_limesurvey_to_qualtrics_question_texts(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert [q.text for q in _all_questions(survey)] == [q.text for q in _all_questions(survey2)]

    def test_limesurvey_to_qualtrics_answer_options(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert _all_option_texts(survey) == _all_option_texts(survey2)

    # ------------------------------------------------------------------
    # Qualtrics → LimeSurvey
    # ------------------------------------------------------------------

    def test_qualtrics_to_limesurvey_question_count(self):
        survey = QualtricsAdapter().import_survey(make_minimal_qsf())
        exported = LimeSurveyAdapter().export_survey(survey)
        survey2 = LimeSurveyAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_qualtrics_to_limesurvey_question_types(self):
        survey = QualtricsAdapter().import_survey(make_minimal_qsf())
        exported = LimeSurveyAdapter().export_survey(survey)
        survey2 = LimeSurveyAdapter().import_survey(exported)
        assert [q.type for q in _all_questions(survey)] == [q.type for q in _all_questions(survey2)]

    def test_qualtrics_to_limesurvey_answer_options(self):
        survey = QualtricsAdapter().import_survey(make_minimal_qsf())
        exported = LimeSurveyAdapter().export_survey(survey)
        survey2 = LimeSurveyAdapter().import_survey(exported)
        assert _all_option_texts(survey) == _all_option_texts(survey2)

    # ------------------------------------------------------------------
    # LimeSurvey → QTI
    # ------------------------------------------------------------------

    def test_limesurvey_to_qti_question_count(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QTIAdapter().export_survey(survey)
        survey2 = QTIAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_limesurvey_to_qti_question_types(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QTIAdapter().export_survey(survey)
        survey2 = QTIAdapter().import_survey(exported)
        assert [q.type for q in _all_questions(survey)] == [q.type for q in _all_questions(survey2)]

    def test_limesurvey_to_qti_answer_options(self):
        survey = LimeSurveyAdapter().import_survey(MINIMAL_LSS)
        exported = QTIAdapter().export_survey(survey)
        survey2 = QTIAdapter().import_survey(exported)
        assert _all_option_texts(survey) == _all_option_texts(survey2)

    # ------------------------------------------------------------------
    # QTI → SurveyMonkey
    # ------------------------------------------------------------------

    def test_qti_to_surveymonkey_question_count(self):
        survey = QTIAdapter().import_survey(MINIMAL_QTI)
        exported = SurveyMonkeyAdapter().export_survey(survey)
        survey2 = SurveyMonkeyAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_qti_to_surveymonkey_question_types(self):
        survey = QTIAdapter().import_survey(MINIMAL_QTI)
        exported = SurveyMonkeyAdapter().export_survey(survey)
        survey2 = SurveyMonkeyAdapter().import_survey(exported)
        assert [q.type for q in _all_questions(survey)] == [q.type for q in _all_questions(survey2)]

    def test_qti_to_surveymonkey_answer_options(self):
        survey = QTIAdapter().import_survey(MINIMAL_QTI)
        exported = SurveyMonkeyAdapter().export_survey(survey)
        survey2 = SurveyMonkeyAdapter().import_survey(exported)
        assert _all_option_texts(survey) == _all_option_texts(survey2)

    # ------------------------------------------------------------------
    # SurveyMonkey → QTI
    # ------------------------------------------------------------------

    def test_surveymonkey_to_qti_question_count(self):
        survey = SurveyMonkeyAdapter().import_survey(make_sm_survey())
        exported = QTIAdapter().export_survey(survey)
        survey2 = QTIAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_surveymonkey_to_qti_question_types(self):
        survey = SurveyMonkeyAdapter().import_survey(make_sm_survey())
        exported = QTIAdapter().export_survey(survey)
        survey2 = QTIAdapter().import_survey(exported)
        assert [q.type for q in _all_questions(survey)] == [q.type for q in _all_questions(survey2)]

    # ------------------------------------------------------------------
    # SurveyMonkey → Qualtrics
    # ------------------------------------------------------------------

    def test_surveymonkey_to_qualtrics_question_count(self):
        survey = SurveyMonkeyAdapter().import_survey(make_sm_survey())
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert len(_all_questions(survey)) == len(_all_questions(survey2))

    def test_surveymonkey_to_qualtrics_question_texts(self):
        survey = SurveyMonkeyAdapter().import_survey(make_sm_survey())
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert [q.text for q in _all_questions(survey)] == [q.text for q in _all_questions(survey2)]

    # ------------------------------------------------------------------
    # Multi-section: section count survives cross-platform
    # ------------------------------------------------------------------

    def test_multi_section_lss_to_qsf_section_count(self):
        survey = LimeSurveyAdapter().import_survey(MULTI_SECTION_LSS)
        exported = QualtricsAdapter().export_survey(survey)
        survey2 = QualtricsAdapter().import_survey(exported)
        assert len(survey.sections) == len(survey2.sections)

    def test_multi_section_qti_to_lss_section_count(self):
        survey = QTIAdapter().import_survey(MULTI_SECTION_QTI)
        exported = LimeSurveyAdapter().export_survey(survey)
        survey2 = LimeSurveyAdapter().import_survey(exported)
        assert len(survey.sections) == len(survey2.sections)
