"""Integration tests for RAG pipeline end-to-end flows."""

import os

import pytest

from cue_api.ingest import ingest_files_into_store
from cue_api.rag_pipeline import RAGPipeline
from m_shared.llm import LLMClient
from m_shared.session import SessionManager


@pytest.fixture
def temp_sessions_dir(tmp_path):
    """Create temporary directory for sessions."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    return sessions_dir


@pytest.fixture
def session_manager(temp_sessions_dir):
    """Create session manager with temporary storage."""
    return SessionManager(base_path=str(temp_sessions_dir))


@pytest.fixture
def llm_client():
    """Create LLM client (uses environment variables for API key)."""
    # Skip if no API key available
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set - skipping integration tests")

    return LLMClient(
        api_key=api_key,
        model_name=os.getenv("DEFAULT_LLM_MODEL", "anthropic/claude-haiku-4.5"),
        temperature=0.4,
    )


@pytest.fixture
def rag_pipeline(session_manager, llm_client):
    """Create RAG pipeline with real dependencies."""
    return RAGPipeline(
        session_manager=session_manager,
        llm_client=llm_client,
        default_top_k=5,
        default_temperature=0.4,
    )


@pytest.fixture
def sample_document(tmp_path):
    """Create sample document file."""
    doc_path = tmp_path / "employment_contract.txt"
    doc_path.write_text(
        """
EMPLOYMENT CONTRACT

Employee: John Doe
Position: Senior Researcher
Department: Computer Science
Start Date: January 1, 2025
Contract Duration: 2 years

Responsibilities:
- Conduct research in artificial intelligence
- Publish papers in peer-reviewed journals
- Supervise graduate students
- Teach undergraduate courses

Salary: €60,000 per year
Benefits: Health insurance, pension plan

This contract is valid from January 1, 2025 to December 31, 2026.
    """.strip()
    )
    return doc_path


@pytest.fixture
def multiple_documents(tmp_path):
    """Create multiple document files."""
    doc1 = tmp_path / "contract.txt"
    doc1.write_text(
        """
EMPLOYMENT CONTRACT
Position: Senior Researcher
Start Date: January 1, 2025
Salary: €60,000 per year
    """.strip()
    )

    doc2 = tmp_path / "benefits.txt"
    doc2.write_text(
        """
BENEFITS PACKAGE
Health insurance: Full coverage
Pension plan: Employer matches 5%
Vacation: 25 days per year
Professional development: €2,000 annual budget
    """.strip()
    )

    return [doc1, doc2]


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_pipeline_single_document(rag_pipeline, session_manager, sample_document, tmp_path):
    """Test complete flow: upload → ingest → suggest → verify citations."""
    # Create session
    session = session_manager.create_session(user_id="user_123")

    # Ingest document
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(sample_document)])

    # Generate suggestion
    result = rag_pipeline.suggest_answer(
        question="What is the employee's job title?", session_id=session.session_id
    )

    # Verify result structure
    assert "answer" in result
    assert "citations" in result
    assert "metadata" in result

    # Verify answer is non-empty
    assert len(result["answer"]) > 0

    # Verify citations
    assert len(result["citations"]) > 0
    citation = result["citations"][0]
    assert "employment_contract.txt" in citation.source_id  # Source may be full path or filename
    assert len(citation.highlights) > 0
    assert "Senior Researcher" in citation.highlights[0] or "Senior Researcher" in result["answer"]

    # Verify metadata
    assert result["metadata"]["session_id"] == session.session_id
    assert result["metadata"]["num_chunks"] > 0


def test_multiple_documents_multi_source_citations(
    rag_pipeline, session_manager, multiple_documents
):
    """Test that suggestions from multiple documents include citations from correct sources."""
    # Create session
    session = session_manager.create_session(user_id="user_456")

    # Ingest documents
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(doc) for doc in multiple_documents])

    # Ask question that requires both documents
    result = rag_pipeline.suggest_answer(
        question="What benefits are included?", session_id=session.session_id
    )

    # Verify answer and citations
    assert len(result["answer"]) > 0
    assert len(result["citations"]) > 0

    # Check that citations reference correct sources
    source_ids = {c.source_id for c in result["citations"]}
    assert any("benefits.txt" in src for src in source_ids)  # Should reference benefits document

    # Verify citation highlights are relevant
    for citation in result["citations"]:
        assert len(citation.highlights[0]) > 0


def test_session_isolation(rag_pipeline, session_manager, sample_document, multiple_documents):
    """Test that suggestions in session A don't leak to session B."""
    # Create two sessions
    session_a = session_manager.create_session(user_id="user_a")
    session_b = session_manager.create_session(user_id="user_b")

    # Ingest different documents to each session
    store_a = session_manager.get_vector_store(session_a.session_id)
    ingest_files_into_store(store=store_a, file_paths=[str(sample_document)])

    store_b = session_manager.get_vector_store(session_b.session_id)
    ingest_files_into_store(store=store_b, file_paths=[str(doc) for doc in multiple_documents])

    # Ask same question in both sessions
    question = "What is the salary?"

    result_a = rag_pipeline.suggest_answer(question, session_a.session_id)
    result_b = rag_pipeline.suggest_answer(question, session_b.session_id)

    # Verify session A only references its document
    sources_a = {c.source_id for c in result_a["citations"]}
    assert any("employment_contract.txt" in src for src in sources_a)
    assert not any("contract.txt" in src and "employment_contract" not in src for src in sources_a)
    assert not any("benefits.txt" in src for src in sources_a)

    # Verify session B only references its documents
    sources_b = {c.source_id for c in result_b["citations"]}
    assert any("contract.txt" in src or "benefits.txt" in src for src in sources_b)
    assert not any("employment_contract.txt" in src for src in sources_b)


def test_no_documents_in_session(rag_pipeline, session_manager):
    """Test graceful handling when session has no documents."""
    # Create empty session
    session = session_manager.create_session(user_id="user_empty")

    # Try to get suggestion
    result = rag_pipeline.suggest_answer(
        question="What is my job title?", session_id=session.session_id
    )

    # Should return message about no information
    assert "couldn't find" in result["answer"].lower()
    assert result["citations"] == []
    assert result["metadata"]["num_chunks"] == 0


def test_malformed_question_handling(rag_pipeline, session_manager, sample_document):
    """Test handling of empty or malformed questions."""
    # Create session with document
    session = session_manager.create_session(user_id="user_test")
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(sample_document)])

    # Test empty question
    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.suggest_answer("", session.session_id)

    # Test whitespace-only question
    with pytest.raises(ValueError, match="Question cannot be empty"):
        rag_pipeline.suggest_answer("   ", session.session_id)


def test_obscure_question_no_relevant_results(rag_pipeline, session_manager, sample_document):
    """Test handling when question doesn't match any document content."""
    # Create session with document
    session = session_manager.create_session(user_id="user_test2")
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(sample_document)])

    # Ask completely unrelated question
    result = rag_pipeline.suggest_answer(
        question="What is the airspeed velocity of an unladen swallow?",
        session_id=session.session_id,
    )

    # Should still get a response (even if it says "I don't know")
    assert len(result["answer"]) > 0

    # May have few or no citations if nothing relevant
    # (ChromaDB will still return something, but with high distance)


def test_citation_accuracy_spot_check(rag_pipeline, session_manager, sample_document):
    """Spot check: Verify that citations actually reference the answer content."""
    # Create session
    session = session_manager.create_session(user_id="user_cite")
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(sample_document)])

    # Ask specific question
    result = rag_pipeline.suggest_answer(
        question="When does the contract start?", session_id=session.session_id
    )

    answer = result["answer"].lower()

    # Check that answer mentions relevant information
    # (This is a simple heuristic - full validation requires manual review)
    assert any(keyword in answer for keyword in ["january", "2025", "start", "date", "begin"])

    # Check that at least one citation highlight is relevant
    highlights = [h for c in result["citations"] for h in c.highlights]
    highlights_text = " ".join(highlights).lower()
    assert any(keyword in highlights_text for keyword in ["january", "2025", "start"])


def test_custom_parameters(rag_pipeline, session_manager, sample_document):
    """Test RAG pipeline with custom top_k and temperature parameters."""
    # Create session
    session = session_manager.create_session(user_id="user_custom")
    store = session_manager.get_vector_store(session.session_id)
    ingest_files_into_store(store=store, file_paths=[str(sample_document)])

    # Use custom parameters
    result = rag_pipeline.suggest_answer(
        question="What is the salary?", session_id=session.session_id, top_k=3, temperature=0.3
    )

    # Verify parameters in metadata
    assert result["metadata"]["top_k"] == 3
    assert result["metadata"]["temperature"] == 0.3

    # Verify we got an answer
    assert len(result["answer"]) > 0
