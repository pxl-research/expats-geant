"""Unit tests for batch suggest models, normalization, and RAG pipeline extensions."""

import pytest

from cue_api.models import (
    BatchChoice,
    BatchSuggestItem,
    BatchSuggestRequest,
    BatchSuggestSection,
    normalize_to_sections,
)
from cue_api.rag_pipeline import RAGPipeline
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
        raw = '{"answer": "Yes, we comply.", "reasoning": "The policy document clearly states compliance."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes, we comply."
        assert reasoning == "The policy document clearly states compliance."
        assert selected_raw is None

    def test_parses_selected_field(self, pipeline):
        raw = '{"answer": "Yes.", "selected": "yes", "reasoning": null}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes."
        assert selected_raw == "yes"
        assert reasoning is None

    def test_selected_none_string_returns_none(self, pipeline):
        raw = '{"answer": "Unclear.", "selected": "NONE", "reasoning": "Ambiguous."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert selected_raw is None

    def test_selected_null_returns_none(self, pipeline):
        raw = '{"answer": "Unclear.", "selected": null, "reasoning": "Ambiguous."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert selected_raw is None

    def test_blank_reasoning_returns_none(self, pipeline):
        raw = '{"answer": "We retain data for 3 years.", "reasoning": null}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "We retain data for 3 years."
        assert reasoning is None

    def test_missing_reasoning_returns_none(self, pipeline):
        raw = '{"answer": "Partial compliance."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Partial compliance."
        assert reasoning is None

    def test_multiline_answer_preserved(self, pipeline):
        raw = '{"answer": "We retain data for 5 years after project completion,\\nconsistent with our research data management policy.", "reasoning": "Policy document section 3 states this clearly."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert "5 years" in answer
        assert "consistent with our research" in answer
        assert reasoning == "Policy document section 3 states this clearly."

    def test_multiline_reasoning_preserved(self, pipeline):
        raw = '{"answer": "Yes.", "reasoning": "The evidence is strong.\\nMultiple sources confirm this."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Yes."
        assert "The evidence is strong." in reasoning
        assert "Multiple sources confirm this." in reasoning

    def test_fallback_when_no_answer_prefix(self, pipeline):
        raw = "Some unstructured response."
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Some unstructured response."
        assert reasoning is None

    # --- New tests (3.2–3.6) ---

    def test_valid_json_all_fields_present(self, pipeline):
        raw = '{"answer": "Full-time employment.", "selected": "opt_a", "reasoning": "Contract section 1 confirms this."}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Full-time employment."
        assert selected_raw == "opt_a"
        assert reasoning == "Contract section 1 confirms this."

    def test_valid_json_with_null_selected_and_reasoning(self, pipeline):
        raw = '{"answer": "Based on the documents, yes.", "selected": null, "reasoning": null}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Based on the documents, yes."
        assert selected_raw is None
        assert reasoning is None

    def test_fenced_json_handled(self, pipeline):
        raw = '```json\n{"answer": "Fenced answer.", "reasoning": "Source is clear."}\n```'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == "Fenced answer."
        assert reasoning == "Source is clear."
        assert selected_raw is None

    def test_malformed_json_falls_back_gracefully(self, pipeline):
        raw = '{"answer": "Broken JSON'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert answer == raw
        assert reasoning is None
        assert selected_raw is None

    def test_multiline_answer_in_json_value(self, pipeline):
        raw = '{"answer": "Line one.\\nLine two.\\nLine three.", "reasoning": null}'
        answer, reasoning, selected_raw = pipeline._parse_structured_response(raw)
        assert "Line one." in answer
        assert "Line two." in answer
        assert "Line three." in answer
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

    # --- List-shaped input (the schema the LLM is now asked to emit) ---

    def test_single_choice_from_list_with_one_id(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(["yes"], choices, multi=False)
        assert selected_id == "yes"
        assert selected_ids is None

    def test_single_choice_from_list_with_multiple_ids_picks_first(self, pipeline, choices, caplog):
        import logging

        caplog.set_level(logging.INFO, logger="cue_api.rag_pipeline")
        selected_id, selected_ids = pipeline._parse_selected_id(
            ["partial", "yes"], choices, multi=False
        )
        assert selected_id == "partial"
        assert selected_ids is None
        assert any("using first (partial)" in r.message for r in caplog.records)

    def test_multi_choice_from_list(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(
            ["yes", "partial"], choices, multi=True
        )
        assert selected_id is None
        assert selected_ids == ["yes", "partial"]

    def test_empty_list_returns_no_selection(self, pipeline, choices):
        single_id, single_ids = pipeline._parse_selected_id([], choices, multi=False)
        multi_id, multi_ids = pipeline._parse_selected_id([], choices, multi=True)
        assert (single_id, single_ids) == (None, None)
        assert (multi_id, multi_ids) == (None, None)

    def test_list_drops_invalid_ids(self, pipeline, choices):
        # Multi: drop the bogus entry, keep the valid ones.
        _, multi_ids = pipeline._parse_selected_id(["yes", "maybe", "partial"], choices, multi=True)
        assert multi_ids == ["yes", "partial"]
        # Single: skip the bogus entry, pick the first valid one.
        single_id, _ = pipeline._parse_selected_id(["maybe", "yes"], choices, multi=False)
        assert single_id == "yes"

    def test_list_with_no_valid_ids_returns_none(self, pipeline, choices):
        _, multi_ids = pipeline._parse_selected_id(["foo", "bar"], choices, multi=True)
        assert multi_ids is None

    # --- JSON-encoded-list string (defensive: model emits the list as a string) ---

    def test_json_string_list_parses(self, pipeline, choices):
        _, multi_ids = pipeline._parse_selected_id('["yes", "partial"]', choices, multi=True)
        assert multi_ids == ["yes", "partial"]

    # --- Legacy bare-string input (model ignores the list shape) ---

    def test_legacy_bare_string_single_choice(self, pipeline, choices):
        selected_id, _ = pipeline._parse_selected_id("yes", choices, multi=False)
        assert selected_id == "yes"

    def test_legacy_bare_string_multi_choice(self, pipeline, choices):
        # Single string against a multi question: still surfaces it.
        _, multi_ids = pipeline._parse_selected_id("yes", choices, multi=True)
        assert multi_ids == ["yes"]

    def test_legacy_bare_string_invalid_id_returns_none(self, pipeline, choices):
        selected_id, _ = pipeline._parse_selected_id("maybe", choices, multi=False)
        assert selected_id is None

    # --- None / falsy / wrong-type inputs ---

    def test_single_choice_none(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(None, choices, multi=False)
        assert (selected_id, selected_ids) == (None, None)

    def test_multi_choice_none(self, pipeline, choices):
        selected_id, selected_ids = pipeline._parse_selected_id(None, choices, multi=True)
        assert (selected_id, selected_ids) == (None, None)


# ---------------------------------------------------------------------------
# API error-branch coverage for /suggest/batch
# ---------------------------------------------------------------------------


class TestSuggestAPIErrorBranches:
    """Cover rag_pipeline=None and exception paths in /suggest/batch."""

    @pytest.fixture
    def jwt_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")
        monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
        return "test-secret-key"

    @pytest.fixture
    def session_manager(self, tmp_path):
        from m_shared.session.manager import SessionManager

        return SessionManager(base_path=str(tmp_path / "sessions"))

    @pytest.fixture
    def mock_llm(self):
        from unittest.mock import MagicMock

        llm = MagicMock()
        llm.model_name = "test-model"
        llm.temperature = 0.4
        return llm

    @pytest.fixture
    def auth_token(self, jwt_secret):
        from m_shared.auth.jwt_handler import create_token

        return create_token(
            user_id="test_user",
            session_id="dev_session_test_user",
            org="test_org",
            roles=["respondent"],
        )

    @pytest.fixture
    def client_no_rag(self, session_manager):
        """App WITHOUT llm_client so rag_pipeline is None."""
        from fastapi.testclient import TestClient

        from cue_api.api import create_app
        from m_shared.auth.middleware import SessionMiddleware

        app = create_app(session_manager=session_manager)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def client_with_rag(self, session_manager, mock_llm):
        """App WITH llm_client so rag_pipeline is initialised."""
        from fastapi.testclient import TestClient

        from cue_api.api import create_app
        from m_shared.auth.middleware import SessionMiddleware

        app = create_app(session_manager=session_manager, llm_client=mock_llm)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return TestClient(app, raise_server_exceptions=False)

    # -- /suggest/batch --

    def test_batch_suggest_no_rag_pipeline(self, client_no_rag, auth_token):
        """POST /suggest/batch with rag_pipeline=None → 500."""
        payload = {
            "assessment_id": "test",
            "items": [{"id": "q1", "type": "open_ended", "prompt": "What?", "choices": []}],
        }
        response = client_no_rag.post(
            "/suggest/batch",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 500
        assert "RAG pipeline not initialized" in response.json()["detail"]

    def test_batch_suggest_value_error(self, client_with_rag, auth_token):
        """POST /suggest/batch when suggest_batch raises ValueError → 404."""
        from unittest.mock import patch

        payload = {
            "assessment_id": "test",
            "items": [{"id": "q1", "type": "open_ended", "prompt": "What?", "choices": []}],
        }
        with patch(
            "cue_api.rag_pipeline.RAGPipeline.suggest_batch",
            side_effect=ValueError("session not found"),
        ):
            response = client_with_rag.post(
                "/suggest/batch",
                json=payload,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        assert response.status_code == 404
        assert "session not found" in response.json()["detail"]
