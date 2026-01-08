"""M-Shared: Common utilities and infrastructure for M-Chat and M-Autofill."""

from m_shared.llm import LLMClient
from m_shared.vectordb import ChromaDocumentStore

__all__ = ["LLMClient", "ChromaDocumentStore"]
