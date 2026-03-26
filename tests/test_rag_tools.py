"""Tests for RAGTools wrappers."""

import pytest

from cue_api.rag_tools import RAGTools
from m_shared.vectordb import ChromaDocumentStore


@pytest.fixture
def store(tmp_path):
    """Isolated ChromaDocumentStore backed by tmp_path to avoid shared in-memory state."""
    return ChromaDocumentStore(path=str(tmp_path / "chroma"))


@pytest.fixture
def store_with_docs(tmp_path):
    """Store with a small document ingested."""
    from cue_api.ingest import ingest_files_into_store

    s = ChromaDocumentStore(path=str(tmp_path / "chroma"))
    doc = tmp_path / "sample.txt"
    doc.write_text("The capital of Belgium is Brussels. It hosts many EU institutions.")
    ingest_files_into_store(file_paths=[str(doc)], store=s)
    return s


class TestRAGTools:
    """Tests for RAGTools methods."""

    def test_list_documents_empty_store(self, store):
        """list_documents on an empty store returns an empty list."""
        tools = RAGTools(store=store)
        assert tools.list_documents() == []

    def test_list_documents_with_ingested_doc(self, store_with_docs):
        """list_documents returns the ingested document name."""
        tools = RAGTools(store=store_with_docs)
        docs = tools.list_documents()
        assert len(docs) == 1
        assert "sample" in docs[0].lower()

    def test_lookup_in_documentation_returns_results(self, store_with_docs):
        """lookup_in_documentation returns relevant chunks for a matching query."""
        tools = RAGTools(store=store_with_docs)
        results = tools.lookup_in_documentation("capital of Belgium")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_lookup_in_documentation_empty_store(self, store):
        """lookup_in_documentation on empty store returns empty list."""
        tools = RAGTools(store=store)
        results = tools.lookup_in_documentation("anything")
        assert results == []

    def test_as_registry_keys(self, store):
        """as_registry returns dict with the expected tool names."""
        tools = RAGTools(store=store)
        registry = tools.as_registry()
        assert "list_documents" in registry
        assert "lookup_in_documentation" in registry

    def test_as_registry_callables(self, store):
        """as_registry values are callable."""
        tools = RAGTools(store=store)
        registry = tools.as_registry()
        assert callable(registry["list_documents"])
        assert callable(registry["lookup_in_documentation"])
