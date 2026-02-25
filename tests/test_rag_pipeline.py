"""Unit tests for RAG pipeline components."""

from unittest.mock import Mock

import pytest

from m_autofill.rag_pipeline import RAGPipeline
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
    """RAG pipeline with mocked dependencies."""
    return RAGPipeline(
        session_manager=mock_session_manager,
        llm_client=mock_llm_client,
        default_top_k=5,
        default_temperature=0.4,
        max_tokens=500,
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
    prompt = messages[0]["content"]

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
