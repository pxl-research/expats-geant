"""RAG tool wrappers (core logic only).

Adapted from `demo_code/demos/tool_calling/tools_rag.py` and `tool_descriptors.py`.

These are intended to be used with OpenAI-compatible tool calling.
"""

from __future__ import annotations

from dataclasses import dataclass

from m_shared.vectordb import ChromaDocumentStore

rag_tool_descriptors = [
    {
        "type": "function",
        "function": {
            "name": "lookup_in_documentation",
            "description": (
                "Search respondent-provided artifacts that were ingested into the evidence store (RAG). "
                "Use a natural-language query. The tool returns snippets with metadata and distances. "
                "When referencing results, include relevant metadata (e.g., source)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query to search for in the evidence store",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List the document collections currently present in the evidence store.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


@dataclass
class RAGTools:
    """A minimal tool set backed by a ChromaDocumentStore."""

    store: ChromaDocumentStore

    def list_documents(self):
        return self.store.list_documents()

    def lookup_in_documentation(self, query: str):
        results = self.store.query_store(query, amount=5)
        return results[:5]

    def as_registry(self) -> dict[str, object]:
        """Return a registry suitable for `run_chat_with_tools` (name -> callable)."""
        return {
            "list_documents": self.list_documents,
            "lookup_in_documentation": self.lookup_in_documentation,
        }
