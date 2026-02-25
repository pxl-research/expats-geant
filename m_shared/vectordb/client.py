"""ChromaDB wrapper for document storage and retrieval."""

import chromadb
from chromadb import QueryResult
from tqdm import tqdm

from m_shared.vectordb.utils import clean_up_string, sanitize_filename


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
            if results[field] is not None:  # type: ignore[literal-required]
                # Remove trailing 's' to singularize field names
                key = field[:-1] if field.endswith("s") else field
                repacked_result[key] = results[field][0][r]  # type: ignore[literal-required]
        repacked.append(repacked_result)

    return repacked


class ChromaDocumentStore:
    """
    ChromaDB wrapper for document storage and retrieval.

    Note: For MVP simplicity this mirrors the demo behavior:
    - One Chroma client (in-memory if no path is provided)
    - One collection per ingested document
    - Query searches across all collections and returns the top-N results
    """

    def __init__(self, path: str | None = None):
        """
        Initialize ChromaDB document store.

        Args:
            path: Path for persistent storage. If None, uses in-memory storage.
        """
        self.path = path

        if path is None:
            self.cdb_client: chromadb.ClientAPI = chromadb.Client()  # in memory
        else:
            self.cdb_client = chromadb.PersistentClient(path=path)

    def add_document(
        self,
        document_name: str,
        chunks: list[str],
        meta_infos: list[dict],
        tqdm_func=tqdm,
    ) -> None:
        """
        Add a document to the store as a collection of chunks.

        Args:
            document_name: Name of the document
            chunks: List of text chunks
            meta_infos: List of metadata dicts (one per chunk)
            tqdm_func: Progress iterator factory (defaults to tqdm)
        """
        collection_name = clean_up_string(document_name)

        if collection_name in self.list_documents():
            print(f"A document with this name is already in the collection: {collection_name}")
            return

        collection = self.cdb_client.create_collection(name=collection_name)

        iterator = tqdm_func(range(len(chunks)))
        if hasattr(iterator, "set_description"):
            iterator.set_description(desc=collection_name)

        for i in iterator:
            metadata = meta_infos[i] if i < len(meta_infos) else {}
            chunk_id = metadata.get("id", f"chunk-{i}")
            collection.add(
                documents=[chunks[i]],
                ids=[chunk_id],
                metadatas=[metadata],
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
        except Exception:  # noqa: S110 - delete-if-exists pattern, absence is fine
            pass

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
        """Search across all collections for the most relevant chunks."""
        all_results = []
        collections = self.cdb_client.list_collections()

        for collection in collections:
            results = collection.query(query_texts=[query_text], n_results=n_results)
            cleaned = repack_query_results(results)
            all_results.extend(cleaned)

        # Sort by distance and return top n_results
        all_results.sort(key=lambda r: r.get("distance", float("inf")))
        return all_results[:n_results]

    def query_with_filter(self, query_text: str, filters: dict, n_results: int = 5) -> list[dict]:
        """Search with optional metadata filters.

        Supports two types of filtering:
        - ``source``: str or list[str] — restrict retrieval to specific document(s),
          matched by filename (without path or extension). More efficient than a
          metadata ``where`` clause because non-matching collections are skipped entirely.
        - Any other key: passed directly as a ChromaDB ``where`` clause, e.g.
          ``{"ingested_at": {"$gte": 1735689600.0}}`` for time-range filtering (Unix timestamp float).

        Args:
            query_text: Semantic search query
            filters: Dict of filter criteria (see above)
            n_results: Maximum number of results to return

        Returns:
            List of matching chunks, ranked by semantic similarity

        Examples:
            >>> # Filter by document source
            >>> results = store.query_with_filter("salary", {"source": "contract.pdf"})
            >>> # Filter by ingestion time range
            >>> results = store.query_with_filter(
            ...     "leave policy",
            ...     {"ingested_at": {"$gte": 1735689600.0}},  # Unix timestamp float
            ... )
        """
        all_results = []
        collections = self.cdb_client.list_collections()

        # Source filter: restrict to matching collections (skip others entirely)
        source_filter = filters.get("source")
        where_filters = {k: v for k, v in filters.items() if k != "source"}

        if source_filter:
            sources = [source_filter] if isinstance(source_filter, str) else list(source_filter)
            allowed_names = {sanitize_filename(s) for s in sources}
        else:
            allowed_names = None

        for collection in collections:
            if allowed_names is not None and collection.name not in allowed_names:
                continue

            count = collection.count()
            if count == 0:
                continue
            actual_n = min(n_results, count)

            query_kwargs = {"query_texts": [query_text], "n_results": actual_n}
            if where_filters:
                query_kwargs["where"] = where_filters

            try:
                results = collection.query(**query_kwargs)  # type: ignore[arg-type]
                all_results.extend(repack_query_results(results))
            except Exception:  # noqa: S112 - skip collections that fail to query
                continue

        all_results.sort(key=lambda r: r.get("distance", float("inf")))
        return all_results[:n_results]

    def cleanup(self) -> None:
        """
        Clean up resources. For ephemeral clients, this marks data for deletion.
        """
        # ChromaDB clients don't require explicit cleanup, but this is here for future use
        # (e.g., when migrating to Redis or other persistent backends)
        pass
