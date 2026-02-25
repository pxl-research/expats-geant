"""Unit tests for batch suggest models, normalization, and RAG pipeline extensions."""

import pytest

from m_autofill.models import (
    BatchChoice,
    BatchSuggestItem,
    BatchSuggestRequest,
    BatchSuggestSection,
    normalize_to_sections,
)
from m_autofill.rag_pipeline import RAGPipeline
from m_shared.models.question import QuestionType

# ---------------------------------------------------------------------------
# BatchSuggestItem validation
# ---------------------------------------------------------------------------


class TestBatchSuggestItem:
    def test_single_choice_with_choices_valid(self):
        item = BatchSuggestItem(
            id="q1",
            type=QuestionType.SINGLE_CHOICE,
            prompt="Yes or no?",
            choices=[BatchChoice(id="yes", label="Yes"), BatchChoice(id="no", label="No")],
        )
        assert len(item.choices) == 2

    def test_multiple_choice_with_choices_valid(self):
        item = BatchSuggestItem(
            id="q1",
            type=QuestionType.MULTIPLE_CHOICE,
            prompt="Pick all that apply.",
            choices=[BatchChoice(id="a", label="A"), BatchChoice(id="b", label="B")],
        )
        assert len(item.choices) == 2

    def test_open_ended_without_choices_valid(self):
        item = BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="Describe your role.")
        assert item.choices == []

    def test_single_choice_without_choices_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BatchSuggestItem(id="q1", type=QuestionType.SINGLE_CHOICE, prompt="Yes or no?")

    def test_multiple_choice_without_choices_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BatchSuggestItem(id="q1", type=QuestionType.MULTIPLE_CHOICE, prompt="Pick all.")

    def test_open_ended_with_choices_raises(self):
        with pytest.raises(ValueError, match="must be empty"):
            BatchSuggestItem(
                id="q1",
                type=QuestionType.OPEN_ENDED,
                prompt="Describe.",
                choices=[BatchChoice(id="a", label="A")],
            )


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestBatchSuggestRequest:
    def test_sections_input_valid(self):
        req = BatchSuggestRequest(
            assessment_id="test",
            sections=[
                BatchSuggestSection(
                    id="s1",
                    items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="What?")],
                )
            ],
        )
        assert req.assessment_id == "test"
        assert len(req.sections) == 1

    def test_flat_items_input_valid(self):
        req = BatchSuggestRequest(
            assessment_id="test",
            items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="What?")],
        )
        assert len(req.items) == 1

    def test_both_sections_and_items_raises(self):
        with pytest.raises(ValueError, match="not both"):
            BatchSuggestRequest(
                assessment_id="test",
                sections=[
                    BatchSuggestSection(
                        id="s1",
                        items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="?")],
                    )
                ],
                items=[BatchSuggestItem(id="q2", type=QuestionType.OPEN_ENDED, prompt="?")],
            )

    def test_neither_sections_nor_items_raises(self):
        with pytest.raises(ValueError, match="either"):
            BatchSuggestRequest(assessment_id="test")

    def test_optional_context(self):
        req = BatchSuggestRequest(
            assessment_id="test",
            context="GDPR questionnaire",
            items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="What?")],
        )
        assert req.context == "GDPR questionnaire"

    def test_optional_section_title(self):
        section = BatchSuggestSection(
            id="s1", items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="What?")]
        )
        assert section.title is None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeToSections:
    def test_sections_returned_as_is(self):
        section = BatchSuggestSection(
            id="s1",
            title="Data",
            items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="What?")],
        )
        req = BatchSuggestRequest(assessment_id="a", sections=[section])
        result = normalize_to_sections(req)
        assert len(result) == 1
        assert result[0].id == "s1"

    def test_flat_items_wrapped_in_implicit_section(self):
        req = BatchSuggestRequest(
            assessment_id="a",
            items=[
                BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="A?"),
                BatchSuggestItem(id="q2", type=QuestionType.OPEN_ENDED, prompt="B?"),
            ],
        )
        result = normalize_to_sections(req)
        assert len(result) == 1
        assert result[0].id == "_implicit"
        assert result[0].title is None
        assert len(result[0].items) == 2

    def test_multiple_sections_preserved(self):
        req = BatchSuggestRequest(
            assessment_id="a",
            sections=[
                BatchSuggestSection(
                    id="s1",
                    items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="A?")],
                ),
                BatchSuggestSection(
                    id="s2",
                    items=[BatchSuggestItem(id="q2", type=QuestionType.OPEN_ENDED, prompt="B?")],
                ),
            ],
        )
        result = normalize_to_sections(req)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# RAGPipeline._parse_structured_response
# ---------------------------------------------------------------------------


class TestParseStructuredResponse:
    @pytest.fixture
    def pipeline(self, tmp_path):
        from unittest.mock import MagicMock

        from m_shared.session.manager import SessionManager

        manager = SessionManager(base_path=str(tmp_path))
        llm = MagicMock()
        llm.model_name = "test-model"
        llm.temperature = 0.4
        return RAGPipeline(session_manager=manager, llm_client=llm)

    def test_parses_answer_and_reasoning(self, pipeline):
        raw = "ANSWER: Yes, we comply.\nREASONING: The policy document clearly states compliance."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes, we comply."
        assert reasoning == "The policy document clearly states compliance."
        assert selected_raw is None

    def test_parses_selected_field(self, pipeline):
        raw = "ANSWER: Yes.\nSELECTED: yes\nREASONING:"
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes."
        assert selected_raw == "yes"
        assert reasoning is None

    def test_selected_none_returns_none(self, pipeline):
        raw = "ANSWER: Unclear.\nSELECTED: NONE\nREASONING: Ambiguous."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert selected_raw is None

    def test_blank_reasoning_returns_none(self, pipeline):
        raw = "ANSWER: We retain data for 3 years.\nREASONING:"
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "We retain data for 3 years."
        assert reasoning is None

    def test_missing_reasoning_returns_none(self, pipeline):
        raw = "ANSWER: Partial compliance."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Partial compliance."
        assert reasoning is None

    def test_multiline_answer_preserved(self, pipeline):
        raw = "ANSWER: We retain data for 5 years after project completion,\nconsistent with our research data management policy.\nREASONING: Policy document section 3 states this clearly."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert "5 years" in answer
        assert "consistent with our research" in answer
        assert reasoning == "Policy document section 3 states this clearly."

    def test_multiline_reasoning_preserved(self, pipeline):
        raw = "ANSWER: Yes.\nREASONING: The evidence is strong.\nMultiple sources confirm this."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes."
        assert "The evidence is strong." in reasoning
        assert "Multiple sources confirm this." in reasoning

    def test_fallback_when_no_answer_prefix(self, pipeline):
        raw = "Some unstructured response."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Some unstructured response."
        assert reasoning is None


# ---------------------------------------------------------------------------
# RAGPipeline._parse_selected_id
# ---------------------------------------------------------------------------


class TestParseSelectedId:
    @pytest.fixture
    def pipeline(self, tmp_path):
        from unittest.mock import MagicMock

        from m_shared.session.manager import SessionManager

        manager = SessionManager(base_path=str(tmp_path))
        llm = MagicMock()
        llm.model_name = "test-model"
        llm.temperature = 0.4
        return RAGPipeline(session_manager=manager, llm_client=llm)

    @pytest.fixture
    def choices(self):
        return [
            BatchChoice(id="yes", label="Yes"),
            BatchChoice(id="no", label="No"),
            BatchChoice(id="partial", label="Partially"),
        ]

    def test_single_choice_valid_id(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id("yes", choices, multi=False)
        assert selected_id == "yes"
        assert selected_ids is None

    def test_single_choice_none(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(None, choices, multi=False)
        assert selected_id is None

    def test_single_choice_invalid_id_falls_back_to_none(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id("maybe", choices, multi=False)
        assert selected_id is None

    def test_multi_choice_valid_ids(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id("yes, partial", choices, multi=True)
        assert selected_id is None
        assert set(selected_ids) == {"yes", "partial"}

    def test_multi_choice_none(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(None, choices, multi=True)
        assert selected_ids is None
