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
    """RAG pipeline with mocked dependencies (rewriting off for existing tests)."""
    return RAGPipeline(
        session_manager=mock_session_manager,
        llm_client=mock_llm_client,
        default_top_k=5,
        default_temperature=0.4,
        max_tokens=500,
        query_rewrite=False,
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
# Tests for query rewriting
# ============================================================================


def _make_item(item_id, prompt, item_type="open_ended", choices=None, label=None):
    """Helper to create item-like objects for rewriting tests."""
    return SimpleNamespace(
        id=item_id,
        prompt=prompt,
        type=SimpleNamespace(value=item_type),
        choices=choices or [],
        label=label,
    )


def _make_choice(choice_id, label):
    return SimpleNamespace(id=choice_id, label=label)


@pytest.fixture
def rewrite_pipeline(mock_session_manager, mock_llm_client):
    """RAG pipeline with rewriting enabled."""
    mock_store = mock_session_manager.get_vector_store.return_value
    mock_store.list_documents.return_value = ["contract.pdf", "cv.docx"]
    mock_llm_client.temperature = 0.4
    return RAGPipeline(
        session_manager=mock_session_manager,
        llm_client=mock_llm_client,
        default_top_k=5,
        default_temperature=0.4,
        max_tokens=500,
        query_rewrite=True,
        rewrite_batch_size=20,
    )


class TestRewriteQueries:
    """Tests for _rewrite_queries() core method."""

    def test_success(self, rewrite_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "What is your current employment status?"),
            _make_item("q2", "How long is your contract?"),
        ]
        mock_llm_client.create_completion.return_value = (
            '{"q1": "employment status", "q2": "contract duration"}'
        )

        result = rewrite_pipeline._rewrite_queries(items, "Employment", ["contract.pdf"])

        assert result["q1"] == "employment status"
        assert result["q2"] == "contract duration"

    def test_partial_response(self, rewrite_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "What is your employment status?"),
            _make_item("q2", "How long is your contract?"),
        ]
        mock_llm_client.create_completion.return_value = '{"q1": "employment status"}'

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "employment status"
        assert result["q2"] == "How long is your contract?"

    def test_malformed_json(self, rewrite_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original question?")]
        mock_llm_client.create_completion.return_value = "not json at all"

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "Original question?"

    def test_llm_exception(self, rewrite_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original question?")]
        mock_llm_client.create_completion.side_effect = Exception("API timeout")

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "Original question?"

    def test_empty_string_in_response(self, rewrite_pipeline, mock_llm_client):
        items = [
            _make_item("q1", "Original question A?"),
            _make_item("q2", "Original question B?"),
        ]
        mock_llm_client.create_completion.return_value = '{"q1": "", "q2": "nationality"}'

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "Original question A?"
        assert result["q2"] == "nationality"

    def test_includes_choices_in_prompt(self, rewrite_pipeline, mock_llm_client):
        choices = [_make_choice("a", "Full-time"), _make_choice("b", "Part-time")]
        items = [_make_item("q1", "What is your status?", "single_choice", choices)]
        mock_llm_client.create_completion.return_value = '{"q1": "employment status"}'

        rewrite_pipeline._rewrite_queries(items, None, [])

        call_args = mock_llm_client.create_completion.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "Full-time" in user_msg
        assert "Part-time" in user_msg

    def test_includes_document_names_in_prompt(self, rewrite_pipeline, mock_llm_client):
        items = [_make_item("q1", "Question?")]
        mock_llm_client.create_completion.return_value = '{"q1": "query"}'

        rewrite_pipeline._rewrite_queries(items, "Section A", ["contract.pdf", "cv.docx"])

        call_args = mock_llm_client.create_completion.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        assert "contract.pdf" in user_msg
        assert "cv.docx" in user_msg
        assert "Section A" in user_msg


class TestRewriteBatchSplitting:
    """Tests for section batch splitting."""

    def test_within_batch_size(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_rewrite=True,
            rewrite_batch_size=5,
        )
        items = [_make_item(f"q{i}", f"Question {i}?") for i in range(3)]
        mock_llm_client.create_completion.return_value = '{"q0": "a", "q1": "b", "q2": "c"}'

        pipeline._rewrite_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.call_count == 1

    def test_exceeding_batch_size(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_rewrite=True,
            rewrite_batch_size=2,
        )
        items = [_make_item(f"q{i}", f"Question {i}?") for i in range(5)]
        mock_llm_client.create_completion.return_value = "{}"

        pipeline._rewrite_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.call_count == 3


class TestRewriteFeatureToggle:
    """Tests for feature toggle."""

    def test_disabled_skips_llm(self, mock_session_manager, mock_llm_client):
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_rewrite=False,
        )
        items = [_make_item("q1", "Question?")]

        result = pipeline._rewrite_queries_for_section(items, None, "sess")

        assert result == {}
        mock_llm_client.create_completion.assert_not_called()

    def test_enabled_calls_llm(self, mock_session_manager, mock_llm_client):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []
        mock_llm_client.temperature = 0.4
        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_rewrite=True,
        )
        items = [_make_item("q1", "Question?")]
        mock_llm_client.create_completion.return_value = '{"q1": "rewritten"}'

        pipeline._rewrite_queries_for_section(items, None, "sess")

        assert mock_llm_client.create_completion.called


class TestRewriteInProcessItem:
    """Tests for rewritten query usage in _process_item."""

    def test_uses_rewritten_query_for_retrieval(self, mock_session_manager, mock_llm_client):
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
            query_rewrite=False,
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
            rewritten_query="employment status",
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
            query_rewrite=False,
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
            rewritten_query="employment status",
        )

        generation_call = mock_llm_client.create_completion.call_args
        user_msg = generation_call[1]["messages"][1]["content"]
        assert original_prompt in user_msg


class TestRewriteAuditLogging:
    """Tests for rewritten query in audit log."""

    def test_audit_includes_rewritten_query(self, mock_session_manager, mock_llm_client):
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
            query_rewrite=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Verbose question?",
            type=QuestionType.OPEN_ENDED,
            choices=[],
            label=None,
        )
        pipeline._process_item(
            item,
            "",
            [],
            "sess",
            "assess",
            None,
            rewritten_query="concise query",
        )

        mock_audit.log_suggestion.assert_called_once()
        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["rewritten_query"] == "concise query"

    def test_audit_no_rewritten_when_disabled(self, mock_session_manager, mock_llm_client):
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
            query_rewrite=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Question?",
            type=QuestionType.OPEN_ENDED,
            choices=[],
            label=None,
        )
        pipeline._process_item(item, "", [], "sess", "assess", None)

        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["rewritten_query"] is None


class TestAuditQuestionLabel:
    """Audit logging should prefer item.label over item.prompt for the
    display 'question' field, without ever using it for LLM generation."""

    def test_label_used_for_audit_question_when_present(
        self, mock_session_manager, mock_llm_client
    ):
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
            query_rewrite=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt=(
                'This is the free-text "Other" answer for the question: "Basic Security"\n'
                "The listed choices already cover:\n- Geen voorkennis\n"
                "Only answer if the correct response is NOT one of the choices above."
            ),
            type=QuestionType.OPEN_ENDED,
            choices=[],
            label="Basic Security, Andere",
        )
        pipeline._process_item(item, "", [], "sess", "assess", None)

        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["question"] == "Basic Security, Andere"
        # The LLM call itself must still receive the full verbose prompt.
        llm_messages = mock_llm_client.create_completion.call_args[1]["messages"]
        user_message = next(m["content"] for m in llm_messages if m["role"] == "user")
        assert "The listed choices already cover" in user_message

    def test_prompt_used_for_audit_question_when_no_label(
        self, mock_session_manager, mock_llm_client
    ):
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
            query_rewrite=False,
        )

        from m_shared.models.question import QuestionType

        item = SimpleNamespace(
            id="q1",
            prompt="Voornaam",
            type=QuestionType.OPEN_ENDED,
            choices=[],
            label=None,
        )
        pipeline._process_item(item, "", [], "sess", "assess", None)

        call_kwargs = mock_audit.log_suggestion.call_args[1]
        assert call_kwargs["question"] == "Voornaam"


class TestRewriteEdgeCases:
    """Tests for edge-case branches in rewriting."""

    def test_empty_llm_response(self, rewrite_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original?")]
        mock_llm_client.create_completion.return_value = ""

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "Original?"

    def test_non_dict_json(self, rewrite_pipeline, mock_llm_client):
        items = [_make_item("q1", "Original?")]
        mock_llm_client.create_completion.return_value = '["not", "a", "dict"]'

        result = rewrite_pipeline._rewrite_queries(items, None, [])

        assert result["q1"] == "Original?"

    def test_rewrite_single_query_enabled(self, rewrite_pipeline, mock_llm_client):
        mock_llm_client.create_completion.return_value = '{"_single": "concise query"}'

        result = rewrite_pipeline._rewrite_single_query("Verbose question?", "sess")

        assert result == "concise query"

    def test_rewrite_single_query_returns_none_when_unchanged(
        self, rewrite_pipeline, mock_llm_client
    ):
        mock_llm_client.create_completion.return_value = '{"_single": "Verbose question?"}'

        result = rewrite_pipeline._rewrite_single_query("Verbose question?", "sess")

        assert result is None

    def test_suggest_batch_with_rewriting(self, mock_session_manager, mock_llm_client):
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
            '{"q1": "rewritten"}',
            '{"answer": "Answer", "reasoning": null}',
        ]

        from cue_api.models import BatchSuggestItem, BatchSuggestSection
        from m_shared.models.question import QuestionType

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=mock_llm_client,
            query_rewrite=True,
        )
        section = BatchSuggestSection(
            id="s1",
            title="Section",
            items=[BatchSuggestItem(id="q1", type=QuestionType.OPEN_ENDED, prompt="Verbose?")],
        )

        results = pipeline.suggest_batch([section], "sess", "assess")

        assert len(results) == 1
        assert results[0]["suggestion"] == "Answer"
        mock_store.query.assert_called_once_with(query_text="rewritten", n_results=5)


class TestRewriteDedicatedClient:
    """Tests for dedicated rewrite LLM client."""

    def test_uses_dedicated_client_when_provided(self, mock_session_manager):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []

        main_client = Mock()
        main_client.temperature = 0.4
        rewrite_client = Mock()
        rewrite_client.temperature = 0.4
        rewrite_client.create_completion.return_value = '{"q1": "rewritten"}'

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=main_client,
            query_rewrite=True,
            rewrite_llm_client=rewrite_client,
        )
        items = [_make_item("q1", "Verbose question?")]

        pipeline._rewrite_queries(items, None, [])

        rewrite_client.create_completion.assert_called_once()
        main_client.create_completion.assert_not_called()

    def test_falls_back_to_main_client_when_no_dedicated(self, mock_session_manager):
        mock_store = mock_session_manager.get_vector_store.return_value
        mock_store.list_documents.return_value = []

        main_client = Mock()
        main_client.temperature = 0.4
        main_client.create_completion.return_value = '{"q1": "rewritten"}'

        pipeline = RAGPipeline(
            session_manager=mock_session_manager,
            llm_client=main_client,
            query_rewrite=True,
        )
        items = [_make_item("q1", "Verbose question?")]

        pipeline._rewrite_queries(items, None, [])

        main_client.create_completion.assert_called_once()
