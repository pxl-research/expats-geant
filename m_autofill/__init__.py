"""M-Autofill module (package scaffold).

This package will host the respondent-side evidence-based assistant.
"""

from m_autofill.ingest import ingest_files_into_store
from m_autofill.rag_tools import RAGTools, rag_tool_descriptors

__all__ = ["ingest_files_into_store", "RAGTools", "rag_tool_descriptors"]
