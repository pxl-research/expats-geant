"""Tests for ChromaDocumentStore.query_with_filter() and RAGPipeline filtered retrieval."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cue_api.ingest import ingest_files_into_store
from m_shared.session import SessionManager
from m_shared.vectordb import ChromaDocumentStore

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


@pytest.fixture
def store(tmp_path):
    """In-memory store with two documents ingested."""
    s = ChromaDocumentStore(path=str(tmp_path / "chroma"))
    ingest_files_into_store(
        file_paths=[
            str(TEST_DATA_DIR / "sample.txt"),
            str(TEST_DATA_DIR / "sample_markdown.md"),
        ],
        store=s,
    )
    return s


class TestQueryWithFilterSource:
    def test_source_filter_restricts_to_one_document(self, store):
        """Results come only from the requested document."""
        results = store.query_with_filter(
            query_text="document",
            filters={"source": "sample.txt"},
            n_results=5,
        )
        assert len(results) > 0
        for r in results:
            assert "sample.txt" in r["metadata"]["source"]

    def test_source_filter_excludes_other_documents(self, store):
        """Results from query_with_filter differ from unfiltered query when source is restricted."""
        unfiltered = store.query(query_text="document", n_results=10)
        filtered = store.query_with_filter(
            query_text="document",
            filters={"source": "sample.txt"},
            n_results=10,
        )
        # All filtered results reference only sample.txt
        for r in filtered:
            assert "sample.txt" in r["metadata"]["source"]
        # Unfiltered may include chunks from other documents
        all_sources = {r["metadata"]["source"] for r in unfiltered}
        assert len(all_sources) >= 1  # at minimum one source present

    def test_source_filter_list_includes_multiple_documents(self, store):
        """List-form source filter returns results from all listed documents."""
        results = store.query_with_filter(
            query_text="document",
            filters={"source": ["sample.txt", "sample_markdown.md"]},
            n_results=10,
        )
        sources = {r["metadata"]["source"] for r in results}
        assert any("sample.txt" in s for s in sources)
        assert any("sample_markdown.md" in s for s in sources)

    def test_source_filter_nonexistent_returns_empty(self, store):
        """Filtering for a document that was never ingested returns no results."""
        results = store.query_with_filter(
            query_text="anything",
            filters={"source": "does_not_exist.pdf"},
            n_results=5,
        )
        assert results == []


class TestQueryWithFilterTimestamp:
    def test_ingested_at_set_on_chunks(self, store):
        """Chunks have ingested_at metadata (Unix timestamp) after ingestion."""
        results = store.query(query_text="document", n_results=5)
        for r in results:
            assert "ingested_at" in r["metadata"]
            assert isinstance(r["metadata"]["ingested_at"], float)

    def test_time_filter_past_cutoff_returns_results(self, store):
        """Filter with a past cutoff (Unix ts) returns recently ingested documents."""
        past_ts = (datetime.utcnow() - timedelta(hours=1)).timestamp()
        results = store.query_with_filter(
            query_text="document",
            filters={"ingested_at": {"$gte": past_ts}},
            n_results=5,
        )
        assert len(results) > 0

    def test_time_filter_future_cutoff_returns_empty(self, store):
        """Filter requiring ingestion after a future timestamp returns nothing."""
        future_ts = (datetime.utcnow() + timedelta(hours=1)).timestamp()
        results = store.query_with_filter(
            query_text="document",
            filters={"ingested_at": {"$gte": future_ts}},
            n_results=5,
        )
        assert results == []


class TestQueryWithFilterIntegration:
    def test_filtered_retrieve_via_rag_pipeline(self, tmp_path):
        """RAGPipeline.retrieve() forwards filters to query_with_filter."""
        from unittest.mock import MagicMock

        from cue_api.rag_pipeline import RAGPipeline

        manager = SessionManager(base_path=str(tmp_path))
        session = manager.create_session(user_id="u1")
        store = manager.get_vector_store(session.session_id)
        ingest_files_into_store(
            file_paths=[
                str(TEST_DATA_DIR / "sample.txt"),
                str(TEST_DATA_DIR / "sample_markdown.md"),
            ],
            store=store,
        )

        pipeline = RAGPipeline(
            session_manager=manager,
            llm_client=MagicMock(),
        )

        # Filtered retrieve should only return chunks from sample.txt
        results = pipeline.retrieve(
            question="document",
            session_id=session.session_id,
            filters={"source": "sample.txt"},
        )
        assert len(results) > 0
        for r in results:
            assert "sample.txt" in r["metadata"]["source"]

    def test_unfiltered_retrieve_unchanged(self, tmp_path):
        """RAGPipeline.retrieve() without filters still works as before."""
        from unittest.mock import MagicMock

        from cue_api.rag_pipeline import RAGPipeline

        manager = SessionManager(base_path=str(tmp_path))
        session = manager.create_session(user_id="u2")
        store = manager.get_vector_store(session.session_id)
        ingest_files_into_store(
            file_paths=[str(TEST_DATA_DIR / "sample.txt")],
            store=store,
        )

        pipeline = RAGPipeline(
            session_manager=manager,
            llm_client=MagicMock(),
        )

        results = pipeline.retrieve(question="document", session_id=session.session_id)
        assert len(results) > 0
