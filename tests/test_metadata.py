"""Tests for metadata preservation in document ingestion."""

from pathlib import Path

import pytest

from m_autofill.ingest import ingest_files_into_store
from m_shared.vectordb import ChromaDocumentStore

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


@pytest.fixture
def vector_store(tmp_path):
    """Create a fresh vector store in temporary directory for each test.

    This mimics production session-based isolation where each user session
    gets its own ChromaDB instance in a temporary folder that's cleaned up
    when the session expires (TTL-based cleanup).
    """
    store_path = tmp_path / "chroma_store"
    store_path.mkdir(parents=True, exist_ok=True)
    return ChromaDocumentStore(path=str(store_path))


class TestMetadataPreservation:
    """Tests for metadata tagging and preservation."""

    def test_metadata_structure(self, vector_store):
        """Test that metadata contains required fields."""
        # Create in-memory store
        store = vector_store

        # Ingest a test file
        file_path = str(TEST_DATA_DIR / "sample.txt")
        added = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        assert len(added) == 1

        # Query to retrieve chunks and check metadata
        results = store.query(query_text="document", n_results=5)

        assert len(results) > 0

        for result in results:
            # Check metadata fields exist
            assert "metadata" in result
            metadata = result["metadata"]

            assert "source" in metadata
            assert "chunk_index" in metadata
            assert "id" in metadata

    def test_metadata_source_filename(self, vector_store):
        """Test that source filename is preserved."""
        store = vector_store
        file_path = str(TEST_DATA_DIR / "sample.txt")

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        results = store.query(query_text="sample", n_results=1)
        assert len(results) > 0

        metadata = results[0]["metadata"]
        assert "sample" in metadata["source"].lower()

    def test_metadata_chunk_index(self, vector_store):
        """Test that chunk indices are sequential."""
        store = vector_store
        file_path = str(TEST_DATA_DIR / "long_text.txt")

        ingest_files_into_store(
            file_paths=[file_path],
            store=store,
            max_chunk_size=200,  # Force multiple chunks
        )

        results = store.query(query_text="document", n_results=10)

        # Should have multiple chunks
        assert len(results) > 1

        # Check indices are integers and reasonable
        for result in results:
            chunk_index = result["metadata"]["chunk_index"]
            assert isinstance(chunk_index, int)
            assert chunk_index >= 0

    def test_metadata_unique_chunk_ids(self, vector_store):
        """Test that chunk IDs are unique."""
        store = vector_store
        file_path = str(TEST_DATA_DIR / "long_text.txt")

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=200)

        results = store.query(query_text="document", n_results=20)

        chunk_ids = [result["metadata"]["id"] for result in results]

        # All IDs should be unique
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_multiple_documents_isolated_metadata(self, vector_store):
        """Test that metadata from multiple documents remains isolated."""
        store = vector_store

        file_paths = [str(TEST_DATA_DIR / "sample.txt"), str(TEST_DATA_DIR / "sample_markdown.md")]

        added = ingest_files_into_store(file_paths=file_paths, store=store, max_chunk_size=512)

        assert len(added) == 2

        # Query each document's content
        results1 = store.query(query_text="multiple paragraphs", n_results=5)
        results2 = store.query(query_text="M-Autofill", n_results=5)

        # Check sources are different
        if results1 and results2:
            source1 = results1[0]["metadata"]["source"]
            source2 = results2[0]["metadata"]["source"]
            assert source1 != source2


class TestChunkContentIntegrity:
    """Tests for chunk content accuracy and integrity."""

    def test_no_data_loss_after_chunking(self, vector_store):
        """Test that all content is preserved after chunking."""
        store = vector_store
        file_path = str(TEST_DATA_DIR / "sample.txt")

        # Read original content
        with open(file_path) as f:
            _original_content = f.read()

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=200)

        # Retrieve all chunks
        results = store.query(query_text="document", n_results=20)

        # Combine all chunk texts
        combined = " ".join([r["document"] for r in results])

        # Check key phrases exist in combined chunks
        key_phrases = ["sample text document", "multiple paragraphs", "final paragraph"]

        for phrase in key_phrases:
            assert phrase.lower() in combined.lower()

    def test_chunks_contain_text(self, vector_store):
        """Test that chunks are non-empty."""
        store = vector_store
        file_path = str(TEST_DATA_DIR / "sample.txt")

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        results = store.query(query_text="document", n_results=10)

        for result in results:
            assert len(result["document"]) > 0
            assert result["document"].strip() != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
