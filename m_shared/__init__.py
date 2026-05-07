"""M-Shared: Common utilities and infrastructure for Shape and Cue."""


def __getattr__(name: str):
    if name == "LLMClient":
        from m_shared.llm import LLMClient

        return LLMClient
    if name == "ChromaDocumentStore":
        from m_shared.vectordb import ChromaDocumentStore

        return ChromaDocumentStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LLMClient", "ChromaDocumentStore"]
