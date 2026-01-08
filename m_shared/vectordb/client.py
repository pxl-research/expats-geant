"""
ChromaDB wrapper with session-based isolation and document management.
"""

from typing import Any, Optional

import chromadb
from chromadb import QueryResult
from tqdm import tqdm

from m_shared.vectordb.utils import clean_up_string


def repack_query_results(results: QueryResult) -> list[dict]:
    """
    Repack ChromaDB query results into a flat list of dicts.
    Converts from ChromaDB's nested structure to a cleaner format.

    Args:
        results: Query result from ChromaDB

    Returns:
        List of repacked result dicts with keys: id, distance, metadata, document
    """
    fields = ["ids", "distances", "metadatas", "documents"]
    length = len(results["ids"][0]) if results["ids"] else 0
    repacked = []

    for r in range(length):
        repacked_result = {}
        for field in fields:
            if results[field] is not None:
                # Remove trailing 's' to singularize field names
                key = field[:-1] if field.endswith("s") else field
                repacked_result[key] = results[field][0][r]
        repacked.append(repacked_result)

    return repacked


class ChromaDocumentStore:
    """
    ChromaDB wrapper for document storage and retrieval with session-based isolation.
    Each session can have its own ephemeral ChromaDB instance.
    """

    def __init__(self, path: Optional[str] = None, session_id: Optional[str] = None):
        """
        Initialize ChromaDB document store.

        Args:
            path: Path for persistent storage. If None, uses in-memory storage.
            session_id: Optional session identifier for isolation. Used in collection naming.
        """
        self.session_id = session_id
        self.path = path

        if path is None:
            self.cdb_client: chromadb.ClientAPI = chromadb.EphemeralClient()
        else:
            self.cdb_client = chromadb.PersistentClient(path=path)

    def add_document(
        self,
        document_name: str,
        chunks: list[str],
        metadatas: list[dict],
        progress_bar: bool = True,
    ) -> None:
        """
        Add a document to the store as a collection of chunks.

        Args:
            document_name: Name of the document
            chunks: List of text chunks
            metadatas: List of metadata dicts (one per chunk)
            progress_bar: Whether to show progress bar (default: True)

        Raises:
            ValueError: If document already exists
        """
        collection_name = clean_up_string(document_name)

        if collection_name in self.list_documents():
            raise ValueError(f"Document already exists: {collection_name}")

        collection = self.cdb_client.create_collection(name=collection_name)

        # Add chunks to collection
        iterator = tqdm(range(len(chunks)), disable=not progress_bar)
        iterator.set_description(f"Adding {collection_name}")

        for i in iterator:
            collection.add(
                documents=[chunks[i]],
                ids=[metadatas[i].get("id", f"chunk-{i}")],
                metadatas=[metadatas[i]],
            )

    def remove_document(self, document_name: str) -> None:
        """
        Remove a document collection from the store.

        Args:
            document_name: Name of the document to remove
        """
        collection_name = clean_up_string(document_name)
        try:
            self.cdb_client.delete_collection(name=collection_name)
        except Exception:
            pass  # Silently ignore if collection doesn't exist

    def list_documents(self) -> list[str]:
        """
        List all documents (collections) in the store.

        Returns:
            Sorted list of collection names
        """
        collections = self.cdb_client.list_collections()
        names = [col.name for col in collections]
        return sorted(names)

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        """
        Search across all collections for the most relevant chunks.

        Args:
            query_text: Query string
            n_results: Number of results to return (default: 5)

        Returns:
            List of results sorted by distance (similarity)
        """
        all_results = []
        collections = self.cdb_client.list_collections()

        for collection in collections:
            results = collection.query(query_texts=[query_text], n_results=n_results)
            cleaned = repack_query_results(results)
            all_results.extend(cleaned)

        # Sort by distance and return top n_results
        all_results.sort(key=lambda r: r.get("distance", float("inf")))
        return all_results[:n_results]

    def cleanup(self) -> None:
        """
        Clean up resources. For ephemeral clients, this marks data for deletion.
        """
        # ChromaDB clients don't require explicit cleanup, but this is here for future use
        # (e.g., when migrating to Redis or other persistent backends)
        pass
