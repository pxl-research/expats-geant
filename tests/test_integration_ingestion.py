"""Integration tests for document ingestion pipeline."""

from pathlib import Path

import pytest

from cue_api.ingest import ingest_files_into_store
from cue_api.validation import FileValidationError, validate_file_or_raise
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


class TestDocumentIngestionIntegration:
    """Integration tests for full upload → extract → chunk → store flow."""

    def test_full_ingestion_flow_single_file(self, vector_store):
        """Test complete ingestion flow for single file."""
        # 1. Validate file
        file_path = str(TEST_DATA_DIR / "sample.txt")
        validate_file_or_raise(file_path)

        # 2. Use provided vector store
        store = vector_store

        # 3. Ingest file
        added = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        # 4. Verify ingestion
        assert len(added) == 1
        assert "sample" in added[0].lower()

        # 5. Query and verify results
        results = store.query(query_text="document", n_results=5)
        assert len(results) > 0

        # 6. Verify metadata
        for result in results:
            assert "metadata" in result
            assert "source" in result["metadata"]
            assert "chunk_index" in result["metadata"]
            assert "document" in result
            assert len(result["document"]) > 0

    def test_full_ingestion_flow_multiple_files(self, vector_store):
        """Test complete ingestion flow for multiple files."""
        file_paths = [
            str(TEST_DATA_DIR / "sample.txt"),
            str(TEST_DATA_DIR / "sample_markdown.md"),
            str(TEST_DATA_DIR / "long_text.txt"),
        ]

        # Validate all files
        for fp in file_paths:
            validate_file_or_raise(fp)

        # Use provided store and ingest
        store = vector_store
        added = ingest_files_into_store(file_paths=file_paths, store=store, max_chunk_size=512)

        # Verify all files ingested
        assert len(added) == 3

        # List documents
        documents = store.list_documents()
        assert len(documents) == 3

        # Query each document's content
        results1 = store.query(query_text="multiple paragraphs", n_results=3)
        results2 = store.query(query_text="Cue", n_results=3)
        results3 = store.query(query_text="chunking algorithm", n_results=3)

        assert len(results1) > 0
        assert len(results2) > 0
        assert len(results3) > 0

    def test_ingestion_with_different_chunk_sizes(self, tmp_path):
        """Test ingestion with various chunk sizes."""
        file_path = str(TEST_DATA_DIR / "long_text.txt")

        # Small chunks - create dedicated store with isolated path
        small_path = tmp_path / "store_small"
        small_path.mkdir()
        store_small = ChromaDocumentStore(path=str(small_path))
        added_small = ingest_files_into_store(
            file_paths=[file_path], store=store_small, max_chunk_size=200
        )

        # Large chunks - create dedicated store with isolated path
        large_path = tmp_path / "store_large"
        large_path.mkdir()
        store_large = ChromaDocumentStore(path=str(large_path))
        added_large = ingest_files_into_store(
            file_paths=[file_path], store=store_large, max_chunk_size=1024
        )

        # Both should succeed
        assert len(added_small) == 1
        assert len(added_large) == 1

        # Small chunks should create more results
        results_small = store_small.query(query_text="document", n_results=50)
        results_large = store_large.query(query_text="document", n_results=50)

        # Generally, smaller chunk size means more chunks
        assert len(results_small) >= len(results_large)

    def test_ingestion_duplicate_prevention(self, vector_store):
        """Test that duplicate files are not re-ingested."""
        file_path = str(TEST_DATA_DIR / "sample.txt")
        store = vector_store

        # Ingest first time
        added1 = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)
        assert len(added1) == 1

        # Ingest again - should skip duplicate
        added2 = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)
        assert len(added2) == 0  # Already exists, not added

        # Total documents should still be 1
        documents = store.list_documents()
        assert len(documents) == 1

    def test_ingestion_error_handling_invalid_file(self):
        """Test that invalid files raise appropriate errors."""
        # Nonexistent file
        with pytest.raises(FileValidationError):
            validate_file_or_raise("/nonexistent/file.txt")

        # Unsupported type (we'll skip actual ingestion if validation fails)
        # This is by design - validation prevents bad files from reaching ingestion

    def test_semantic_search_after_ingestion(self, vector_store):
        """Test semantic search retrieves relevant content."""
        file_path = str(TEST_DATA_DIR / "sample_markdown.md")
        store = vector_store

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        # Search for specific content
        results = store.query(query_text="introduction section", n_results=3)

        assert len(results) > 0

        # Top result should contain introduction-related content
        top_result = results[0]["document"]
        assert "introduction" in top_result.lower() or "section" in top_result.lower()

    def test_metadata_query_after_ingestion(self, vector_store):
        """Test metadata is queryable after ingestion."""
        file_path = str(TEST_DATA_DIR / "long_text.txt")
        store = vector_store

        ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=300)

        # Get all chunks for this document
        results = store.query(query_text="text", n_results=20)

        # Verify we got multiple chunks with sequential indices
        chunk_indices = [r["metadata"]["chunk_index"] for r in results]
        assert len(set(chunk_indices)) > 1  # Multiple unique indices
        assert min(chunk_indices) >= 0
        assert all(isinstance(idx, int) for idx in chunk_indices)

    def test_end_to_end_with_validation(self, vector_store):
        """Test complete end-to-end flow with validation."""
        # Phase 1: Validation
        file_path = str(TEST_DATA_DIR / "sample.txt")

        try:
            validate_file_or_raise(file_path)
        except FileValidationError as e:
            pytest.fail(f"File validation failed: {e}")

        # Phase 2: Ingestion
        store = vector_store
        added = ingest_files_into_store(file_paths=[file_path], store=store, max_chunk_size=512)

        assert len(added) == 1

        # Phase 3: Retrieval
        results = store.query(query_text="sample document", n_results=5)
        assert len(results) > 0

        # Phase 4: Metadata verification
        for result in results:
            metadata = result["metadata"]
            assert "source" in metadata
            assert "chunk_index" in metadata
            assert isinstance(metadata["chunk_index"], int)

            document_text = result["document"]
            assert len(document_text) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
