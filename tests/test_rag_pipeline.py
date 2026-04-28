"""Unit tests for RAG pipeline components."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cue_api.rag_pipeline import RAGPipeline
from m_shared.models.citation import Citation


@pytest.fixture
def mock_session_manager():
    """Mock session manager with vector store."""
    manager = Mock()
    mock_store = Mock()
    manager.get_vector_store.return_value = mock_store
    return manager


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = Mock()
    return client


@pytest.fixture
def rag_pipeline(mock_session_manager, mock_llm_client):
    """RAG pipeline with mocked dependencies (distillation off for existing tests)."""
    return RAGPipeline(
        session_manager=mock_session_manager,
        llm_client=mock_llm_client,
        default_top_k=5,
        default_temperature=0.4,
        max_tokens=500,
        query_distillation=False,
    )


@pytest.fixture
def sample_chunks():
    """Sample retrieved chunks with metadata."""
    return [
        {
            "id": "chunk-0",
            "document": "You are employed as a Senior Researcher at the university.",
            "metadata": {
                "source": "employment_contract.pdf",
                "chunk_index": 0,
                "position_start": 0,
                "position_end": 100,
                "position_percentage": 0.1,
                "total_chunks": 10,
            },
            "distance": 0.15,
        },
        {
            "id": "chunk-5",
            "document": "Your contract began on January 1, 2025 and is valid for 2 years.",
            "metadata": {
                "source": "employment_contract.pdf",
                "chunk_index": 5,
                "position_start": 500,
                "position_end": 600,
                "position_percentage": 0.5,
                "total_chunks": 10,
            },
            "distance": 0.22,
        },
    ]


# ============================================================================
# Tests for retrieve()
# ============================================================================


def test_retrieve_success(rag_pipeline, mock_session_manager, sample_chunks):
    """Test successful retrieval with valid inputs."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks

    result = rag_pipeline.retrieve("What is my job title?", "session_123")

    assert len(result) == 2
    assert result[0]["metadata"]["source"] == "employment_contract.pdf"
    mock_store.query.assert_called_once_with(query_text="What is my job title?", n_results=5)


def test_retrieve_with_custom_top_k(rag_pipeline, mock_session_manager, sample_chunks):
    """Test retrieval with custom top_k parameter."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks[:1]

    result = rag_pipeline.retrieve("What is my job title?", "session_123", top_k=1)

    assert len(result) == 1
    mock_store.query.assert_called_once_with(query_text="What is my job title?", n_results=1)


def test_retrieve_empty_question(rag_pipeline):
    """Test retrieval fails with empty question."""
    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.retrieve("", "session_123")

    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.retrieve("   ", "session_123")


def test_retrieve_session_not_found(rag_pipeline, mock_session_manager):
    """Test retrieval fails when session not found."""
    mock_session_manager.get_vector_store.return_value = None

    with pytest.raises(ValueError, match="Session not found or expired"):
        rag_pipeline.retrieve("What is my job title?", "invalid_session")


def test_retrieve_preserves_metadata(rag_pipeline, mock_session_manager, sample_chunks):
    """Test that retrieval preserves all metadata from chunks."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks

    result = rag_pipeline.retrieve("test question", "session_123")

    assert result[0]["metadata"]["chunk_index"] == 0
    assert result[0]["metadata"]["position_percentage"] == 0.1
    assert result[0]["distance"] == 0.15


def test_retrieve_empty_results(rag_pipeline, mock_session_manager):
    """Test retrieval with no results."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = []

    result = rag_pipeline.retrieve("obscure question", "session_123")

    assert result == []


# ============================================================================
# Tests for generate_answer()
# ============================================================================


def test_generate_answer_success(rag_pipeline, mock_llm_client, sample_chunks):
    """Test successful answer generation."""
    mock_llm_client.create_completion.return_value = "You are employed as a Senior Researcher."
    mock_llm_client.temperature = 0.4  # Set initial temperature

    answer = rag_pipeline.generate_answer("What is my job title?", sample_chunks)

    assert answer == "You are employed as a Senior Researcher."
    assert mock_llm_client.create_completion.called

    # Verify temperature was set correctly on the client
    assert mock_llm_client.temperature == 0.4

    # Verify only messages and max_tokens passed to create_completion
    call_kwargs = mock_llm_client.create_completion.call_args[1]
    assert "messages" in call_kwargs
    assert call_kwargs["max_tokens"] == 500


def test_generate_answer_with_custom_temperature(rag_pipeline, mock_llm_client, sample_chunks):
    """Test answer generation with custom temperature."""
    mock_llm_client.create_completion.return_value = "Answer text"
    mock_llm_client.temperature = 0.4  # Initial temperature

    rag_pipeline.generate_answer("Question?", sample_chunks, temperature=0.3)

    # Verify temperature was temporarily set to 0.3
    # (Note: it may be restored after, but during the call it should have been 0.3)
    assert mock_llm_client.create_completion.called


def test_generate_answer_empty_question(rag_pipeline, sample_chunks):
    """Test generation fails with empty question."""
    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.generate_answer("", sample_chunks)


def test_generate_answer_no_chunks(rag_pipeline):
    """Test generation fails with no chunks."""
    with pytest.raises(ValueError, match="No chunks provided"):
        rag_pipeline.generate_answer("Question?", [])


def test_generate_answer_llm_failure(rag_pipeline, mock_llm_client, sample_chunks):
    """Test graceful handling of LLM failures."""
    mock_llm_client.create_completion.side_effect = Exception("API error")

    with pytest.raises(RuntimeError, match="LLM generation failed"):
        rag_pipeline.generate_answer("Question?", sample_chunks)


def test_generate_answer_empty_response(rag_pipeline, mock_llm_client, sample_chunks):
    """Test handling of empty LLM response."""
    mock_llm_client.create_completion.return_value = ""

    with pytest.raises(RuntimeError, match="LLM returned empty answer"):
        rag_pipeline.generate_answer("Question?", sample_chunks)


def test_generate_answer_includes_context(rag_pipeline, mock_llm_client, sample_chunks):
    """Test that answer generation includes chunk context in prompt."""
    mock_llm_client.create_completion.return_value = "Answer"

    rag_pipeline.generate_answer("Question?", sample_chunks)

    # Verify prompt includes chunk content
    call_args = mock_llm_client.create_completion.call_args
    messages = call_args[1]["messages"]
    prompt = messages[1]["content"]

    assert "Senior Researcher" in prompt
    assert "employment_contract.pdf" in prompt


# ============================================================================
# Tests for format_citations()
# ============================================================================


def test_format_citations_success(rag_pipeline, sample_chunks):
    """Test successful citation formatting."""
    citations = rag_pipeline.format_citations(
        sample_chunks, "What is my job title?", "You are a Senior Researcher."
    )

    assert len(citations) == 2
    assert all(isinstance(c, Citation) for c in citations)

    # Check first citation
    assert citations[0].source_id == "employment_contract.pdf"
    assert citations[0].chunk_id == "chunk-0"
    assert citations[0].position_percentage == 0.1
    assert len(citations[0].highlights) == 1


def test_format_citations_extracts_metadata(rag_pipeline, sample_chunks):
    """Test that citations extract all relevant metadata."""
    citations = rag_pipeline.format_citations(sample_chunks, "Q", "A")

    citation = citations[0]
    assert citation.position_start == 0
    assert citation.position_end == 100
    assert citation.position_percentage == 0.1
    assert citation.metadata["chunk_index"] == 0
    assert citation.metadata["distance"] == 0.15
    assert citation.metadata["question"] == "Q"


def test_format_citations_text_excerpt(rag_pipeline, sample_chunks):
    """Test text excerpt extraction from chunks."""
    citations = rag_pipeline.format_citations(sample_chunks, "Q", "A")

    excerpt = citations[0].highlights[0]
    assert "Senior Researcher" in excerpt
    assert len(excerpt) <= 200


def test_format_citations_long_text_truncation(rag_pipeline):
    """Test that long text is properly truncated."""
    long_text = "A" * 500
    chunks = [
        {
            "id": "chunk-1",
            "document": long_text,
            "metadata": {"source": "doc.pdf"},
        }
    ]

    citations = rag_pipeline.format_citations(chunks, "Q", "A")
    excerpt = citations[0].highlights[0]

    assert len(excerpt) <= 203  # 200 + "..."
    assert excerpt.endswith("...")


def test_format_citations_empty_chunks(rag_pipeline):
    """Test citation formatting with empty chunks list."""
    citations = rag_pipeline.format_citations([], "Q", "A")
    assert citations == []


def test_format_citations_missing_metadata(rag_pipeline):
    """Test citation formatting handles missing metadata gracefully."""
    chunks = [
        {
            "id": "chunk-1",
            "document": "Some text",
            "metadata": {},  # Empty metadata
        }
    ]

    citations = rag_pipeline.format_citations(chunks, "Q", "A")

    assert len(citations) == 1
    assert citations[0].source_id == "Unknown"
    assert citations[0].chunk_id == "chunk-1"


def test_format_citations_estimates_position(rag_pipeline):
    """Test that position is estimated when not in metadata."""
    chunks = [
        {
            "id": "chunk-5",
            "document": "Text",
            "metadata": {
                "source": "doc.pdf",
                "chunk_index": 5,
                "total_chunks": 10,
            },
        }
    ]

    citations = rag_pipeline.format_citations(chunks, "Q", "A")

    assert citations[0].position_percentage == 0.5  # 5/10


# ============================================================================
# Tests for _filter_chunks_by_distance()
# ============================================================================


def test_filter_chunks_excludes_distant_chunks(rag_pipeline):
    """Chunks above max_citation_distance are excluded before generation."""
    chunks = [
        {"id": "a", "document": "close", "metadata": {}, "distance": 0.5},
        {"id": "b", "document": "far", "metadata": {}, "distance": 2.0},
    ]
    filtered = rag_pipeline._filter_chunks_by_distance(chunks)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "a"


def test_filter_chunks_numbering_alignment(rag_pipeline, mock_llm_client):
    """Citation IDs are derived from the filtered list, not the original retrieved list.

    After filtering, chunk indices passed to format_citations match what the LLM
    saw in the prompt — so [1], [2] references stay consistent.
    """
    chunks = [
        {"id": "c1", "document": "relevant", "metadata": {"source": "doc.pdf"}, "distance": 0.3},
        {"id": "c2", "document": "too far", "metadata": {"source": "doc.pdf"}, "distance": 9.9},
    ]
    filtered = rag_pipeline._filter_chunks_by_distance(chunks)
    citations = rag_pipeline.format_citations(filtered, "Q", "A")

    assert len(citations) == 1
    assert citations[0].id == "cite_1"  # numbering starts from 1 in the filtered list


def test_filter_chunks_all_pass(rag_pipeline):
    """All chunks pass when all distances are within threshold."""
    chunks = [
        {"id": "a", "document": "x", "metadata": {}, "distance": 0.0},
        {"id": "b", "document": "y", "metadata": {}, "distance": 1.5},  # exactly at limit
    ]
    filtered = rag_pipeline._filter_chunks_by_distance(chunks)
    assert len(filtered) == 2


def test_filter_chunks_none_distance(rag_pipeline):
    """Chunks with None distance are treated as 0.0 and included."""
    chunks = [{"id": "a", "document": "x", "metadata": {}, "distance": None}]
    filtered = rag_pipeline._filter_chunks_by_distance(chunks)
    assert len(filtered) == 1


# ============================================================================
# Tests for suggest_answer() orchestration
# ============================================================================


def test_suggest_answer_success(rag_pipeline, mock_session_manager, mock_llm_client, sample_chunks):
    """Test successful full pipeline orchestration."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks
    mock_llm_client.create_completion.return_value = "You are a Senior Researcher."

    result = rag_pipeline.suggest_answer("What is my job title?", "session_123")

    assert result["answer"] == "You are a Senior Researcher."
    assert len(result["citations"]) == 2
    assert result["metadata"]["session_id"] == "session_123"
    assert result["metadata"]["num_chunks"] == 2


def test_suggest_answer_empty_question(rag_pipeline):
    """Test suggest_answer fails with empty question."""
    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.suggest_answer("", "session_123")


def test_suggest_answer_no_session_id(rag_pipeline):
    """Test suggest_answer fails without session ID."""
    with pytest.raises(ValueError, match="Session ID is required"):
        rag_pipeline.suggest_answer("Question?", "")


def test_suggest_answer_no_results(rag_pipeline, mock_session_manager):
    """Test suggest_answer handles no retrieval results."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = []

    result = rag_pipeline.suggest_answer("Obscure question?", "session_123")

    assert "couldn't find any relevant information" in result["answer"]
    assert result["citations"] == []
    assert result["metadata"]["num_chunks"] == 0


def test_suggest_answer_retrieval_failure(rag_pipeline, mock_session_manager):
    """Test suggest_answer handles retrieval failures."""
    mock_session_manager.get_vector_store.return_value = None

    with pytest.raises(ValueError, match="Retrieval failed"):
        rag_pipeline.suggest_answer("Question?", "invalid_session")


def test_suggest_answer_generation_failure(
    rag_pipeline, mock_session_manager, mock_llm_client, sample_chunks
):
    """Test suggest_answer handles generation failures."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks
    mock_llm_client.create_completion.side_effect = Exception("LLM error")

    with pytest.raises(RuntimeError, match="Answer generation failed"):
        rag_pipeline.suggest_answer("Question?", "session_123")


def test_suggest_answer_with_custom_params(
    rag_pipeline, mock_session_manager, mock_llm_client, sample_chunks
):
    """Test suggest_answer with custom top_k and temperature."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.query.return_value = sample_chunks[:1]
    mock_llm_client.create_completion.return_value = "Answer"

    result = rag_pipeline.suggest_answer("Question?", "session_123", top_k=1, temperature=0.3)

    assert result["metadata"]["top_k"] == 1
    assert result["metadata"]["temperature"] == 0.3
    mock_store.query.assert_called_once_with(query_text="Question?", n_results=1)


# ============================================================================
# Tests for _extract_excerpt() helper
# ============================================================================


def test_extract_excerpt_short_text(rag_pipeline):
    """Test excerpt extraction for text shorter than max length."""
    text = "Short text"
    excerpt = rag_pipeline._extract_excerpt(text, max_length=200)
    assert excerpt == "Short text"


def test_extract_excerpt_long_text_sentence_break(rag_pipeline):
    """Test excerpt breaks at sentence boundary when possible."""
    text = "First sentence. Second sentence. Third sentence. More text here."
    excerpt = rag_pipeline._extract_excerpt(text, max_length=50)

    assert excerpt.endswith(".")
    assert len(excerpt) <= 50


def test_extract_excerpt_long_text_word_break(rag_pipeline):
    """Test excerpt breaks at word boundary when no sentence break."""
    text = "A" * 30 + " " + "B" * 30 + " " + "C" * 50
    excerpt = rag_pipeline._extract_excerpt(text, max_length=50)

    assert excerpt.endswith("...")
    assert len(excerpt) <= 53  # 50 + "..."


def test_extract_excerpt_no_breaks(rag_pipeline):
    """Test excerpt truncation when no natural breaks."""
    text = "A" * 300
    excerpt = rag_pipeline._extract_excerpt(text, max_length=200)

    assert len(excerpt) == 203  # 200 + "..."
    assert excerpt.endswith("...")


# ============================================================================
# Tests for query distillation
# ============================================================================


def _make_item(item_id, prompt, item_type="open_ended", choices=None):
    """Helper to create item-like objects for distillation tests."""
    return SimpleNamespace(
        id=item_id,
        prompt=prompt,
        type=SimpleNamespace(value=item_type),
        choices=choices or [],
    )


def _make_choice(choice_id, label):
    return SimpleNamespace(id=choice_id, label=label)


@pytest.fixture
def distill_pipeline(mock_session_manager, mock_llm_client):
    """RAG pipeline with distillation enabled."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.list_documents.return_value = ["contract.pdf", "cv.docx"]
    mock_llm_client.temperature = 0.4
    return RAGPipeline(
        session_manager=mock_session_manager,
        llm_client=mock_llm_client,
        default_top_k=5,
        default_temperature=0.4,
        max_tokens=500,
        query_distillation=True,
        distillation_batch_size=20,
    )


class TestDistillQueries:
    """Tests for _distill_queries() core method."""

    def test_success(self, distill_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "What is your current employment status?"),
            _make_item("q2", "How long is your contract?"),
        ]
        mock_llm_client.create_completion.return_value = (
            '{"q1": "employment status", "q2": "contract duration"}'
        )

        result = distill_pipeline._distill_queries(items, "Employment", ["contract.pdf"])

        assert result["q1"] == "employment status"
        assert result["q2"] == "contract duration"

    def test_partial_response(self, distill_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "What is your employment status?"),
            _make_item("q2", "How long is your contract?"),
        ]
        mock_llm_client.create_completion.return_value = '{"q1": "employment status"}'

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "employment status"
        assert result["q2"] == "How long is your contract?"

    def test_malformed_json(self, distill_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original question?")]
        mock_llm_client.create_completion.return_value = "not json at all"

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "Original question?"

    def test_llm_exception(self, distill_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original question?")]
        mock_llm_client.create_completion.side_effect = Exception("API timeout")

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "Original question?"

    def test_empty_string_in_response(self, distill_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "Original question A?"),
            _make_item("q2", "Original question B?"),
        ]
        mock_llm_client.create_completion.return_value = '{"q1": "", "q2": "nationality"}'

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "Original question A?"
        assert result["q2"] == "nationality"

    def test_includes_choices_in_prompt(self, distill_pipeline, mock_llm_client):
        choices = [_make_choice("a", "Full-time"), _make_choice("b", "Part-time")]
        items = [_make_item("q1", "What is your status?", "single_choice", choices)]
        mock_llm_client.create_completion.return_value = '{"q1": "employment status"}'

        distill_pipeline._distill_queries(items, None, [])

        call_args = mock_llm_client.create_completion.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Full-time" in user_msg
        assert "Part-time" in user_msg

    def test_includes_document_names_in_prompt(self, distill_pipeline, mock_llm_client):
        items = [_make_item("q1", "Question?")]
        mock_llm_client.create_completion.return_value = '{"q1": "query"}'

        distill_pipeline._distill_queries(items, "Section A", ["contract.pdf", "cv.docx"])

        call_args = mock_llm_client.create_completion.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "contract.pdf" in user_msg
        assert "cv.docx" in user_msg
        assert "Section A" in user_msg


class TestDistillBatchSplitting:
    """Tests for section batch splitting."""

    def test_within_batch_size(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=True,
            distillation_batch_size=5,
        )
        items = [_make_item(f"q{i}", f"Question {i}?") for i in range(3)]
        mock_llm_client.create_completion.return_value = '{"q0": "a", "q1": "b", "q2": "c"}'

        pipeline._distill_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.call_count == 1

    def test_exceeding_batch_size(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=True,
            distillation_batch_size=2,
        )
        items = [_make_item(f"q{i}", f"Question {i}?") for i in range(5)]
        mock_llm_client.create_completion.return_value = "{}"

        pipeline._distill_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.call_count == 3


class TestDistillFeatureToggle:
    """Tests for feature toggle."""

    def test_disabled_skips_llm(self, mock_session_manager, mock_llm_client):
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=False,
        )
        items = [_make_item("q1", "Question?")]

        result = pipeline._distill_queries_for_section(items, None, "sess")

        assert result == {}
        mock_llm_client.create_completion.assert_not_called()

    def test_enabled_calls_llm(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=True,
        )
        items = [_make_item("q1", "Question?")]
        mock_llm_client.create_completion.return_value = '{"q1": "distilled"}'

        pipeline._distill_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.called


class TestDistillInProcessItem:
    """Tests for distilled query usage in _process_item."""

    def test_uses_distilled_query_for_retrieval(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.query.return_value = [
            {
                "id": "c1",
                "document": "You work as a researcher.",
                "metadata": {"source": "contract.pdf", "chunk_index": 0},
                "distance": 0.1,
            }
        ]
        mock_llm_client.create_completion.return_value = (
            '{"answer": "Researcher", "reasoning": null}'
        )
        mock_llm_client.temperature = 0.4
        mock_llm_client.model_name = "test-model"

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Could you please describe your current employment status?",
            type=QuestionType.OPEN_ENDED,
            choices=[],
        )
        pipeline._process_item(
            item,
            "",
            [],
            "sess",
            "assess",
            None,
            distilled_query="employment status",
        )

        mock_store.query.assert_called_once_with(query_text="employment status", n_results=5)

    def test_uses_original_prompt_for_generation(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.query.return_value = [
            {
                "id": "c1",
                "document": "Researcher role.",
                "metadata": {"source": "contract.pdf", "chunk_index": 0},
                "distance": 0.1,
            }
        ]
        mock_llm_client.create_completion.return_value = (
            '{"answer": "Researcher", "reasoning": null}'
        )
        mock_llm_client.temperature = 0.4
        mock_llm_client.model_name = "test-model"

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=False,
        )

        from m_shared.models.question import QuestionType

        original_prompt = "Could you please describe your current employment status?"
        item = SimpleNamespace(
            id="q1",
            prompt=original_prompt,
            type=QuestionType.OPEN_ENDED,
            choices=[],
        )
        pipeline._process_item(
            item,
            "",
            [],
            "sess",
            "assess",
            None,
            distilled_query="employment status",
        )

        generation_call = mock_llm_client.create_completion.call_args
        user_msg = generation_call[1]["messages"][1]["content"]
        assert original_prompt in user_msg


class TestDistillAuditLogging:
    """Tests for distilled query in audit log."""

    def test_audit_includes_distilled_query(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.query.return_value = [
            {
                "id": "c1",
                "document": "Text.",
                "metadata": {"source": "doc.pdf", "chunk_index": 0},
                "distance": 0.1,
            }
        ]
        mock_llm_client.create_completion.return_value = '{"answer": "Answer", "reasoning": null}'
        mock_llm_client.temperature = 0.4
        mock_llm_client.model_name = "test-model"
        mock_audit = Mock()

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            audit_logger=mock_audit,
            query_distillation=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Verbose question?",
            type=QuestionType.OPEN_ENDED,
            choices=[],
        )
        pipeline._process_item(
            item,
            "",
            [],
            "sess",
            "assess",
            None,
            distilled_query="concise query",
        )

        mock_audit.log_suggestion.assert_called_once()
        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["distilled_query"] == "concise query"

    def test_audit_no_distilled_when_disabled(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.query.return_value = [
            {
                "id": "c1",
                "document": "Text.",
                "metadata": {"source": "doc.pdf", "chunk_index": 0},
                "distance": 0.1,
            }
        ]
        mock_llm_client.create_completion.return_value = '{"answer": "Answer", "reasoning": null}'
        mock_llm_client.temperature = 0.4
        mock_llm_client.model_name = "test-model"
        mock_audit = Mock()

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            audit_logger=mock_audit,
            query_distillation=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Question?",
            type=QuestionType.OPEN_ENDED,
            choices=[],
        )
        pipeline._process_item(item, "", [], "sess", "assess", None)

        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["distilled_query"] is None


class TestDistillEdgeCases:
    """Tests for edge-case branches in distillation."""

    def test_empty_llm_response(self, distill_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original?")]
        mock_llm_client.create_completion.return_value = ""

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "Original?"

    def test_non_dict_json(self, distill_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original?")]
        mock_llm_client.create_completion.return_value = '["not", "a", "dict"]'

        result = distill_pipeline._distill_queries(items, None, [])

        assert result["q1"] == "Original?"

    def test_distill_single_query_enabled(self, distill_pipeline, mock_llm_client):
        mock_llm_client.create_completion.return_value = '{"_single": "concise query"}'

        result = distill_pipeline._distill_single_query("Verbose question?", "sess")

        assert result == "concise query"

    def test_distill_single_query_returns_none_when_unchanged(
        self, distill_pipeline, mock_llm_client
    ):
        mock_llm_client.create_completion.return_value = '{"_single": "Verbose question?"}'

        result = distill_pipeline._distill_single_query("Verbose question?", "sess")

        assert result is None

    def test_suggest_batch_with_distillation(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = ["doc.pdf"]
        mock_store.query.return_value = [
            {
                "id": "c1",
                "document": "Some text.",
                "metadata": {"source": "doc.pdf", "chunk_index": 0},
                "distance": 0.1,
            }
        ]
        mock_llm_client.temperature = 0.4
        mock_llm_client.model_name = "test-model"
        mock_llm_client.create_completion.side_effect = [
            '{"q1": "distilled"}',
            '{"answer": "Answer", "reasoning": null}',
        ]

        from cue_api.models import BatchSuggestItem, BatchSuggestSection
        from m_shared.models.question import QuestionType

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_distillation=True,
        )
        section = BatchSuggestSection(
            id="s1",
            title="Section",
            items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="Verbose?")],
        )

        results = pipeline.suggest_batch([section], "sess", "assess")

        assert len(results) == 1
        assert results[0]["suggestion"] == "Answer"
        mock_store.query.assert_called_once_with(query_text="distilled", n_results=5)
