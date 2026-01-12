"""RAG (Retrieval-Augmented Generation) pipeline for answer suggestions with citations.

This module orchestrates the complete RAG flow:
1. Semantic retrieval from ChromaDB (session-scoped)
2. LLM-based answer generation from retrieved passages
3. Citation formatting with source metadata and text excerpts

All operations are session-isolated to ensure user privacy and data separation.
"""

from datetime import datetime
from typing import Optional

from m_shared.llm import LLMClient
from m_shared.models.citation import Citation
from m_shared.session import SessionManager
from m_shared.vectordb import ChromaDocumentStore


class RAGPipeline:
    """RAG pipeline for generating answer suggestions with citations.
    
    Examples:
        >>> pipeline = RAGPipeline(session_manager=manager, llm_client=client)
        >>> result = pipeline.suggest_answer(
        ...     question="What is my employment status?",
        ...     session_id="abc123"
        ... )
        >>> print(result["answer"])
        >>> for citation in result["citations"]:
        ...     print(f"Source: {citation.source_id}")
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        llm_client: LLMClient,
        default_top_k: int = 5,
        default_temperature: float = 0.4,
        max_tokens: int = 500,
    ):
        """Initialize RAG pipeline.
        
        Args:
            session_manager: Session manager for accessing vector stores
            llm_client: LLM client for answer generation
            default_top_k: Default number of chunks to retrieve
            default_temperature: Temperature for LLM generation (0.3-0.5 for determinism)
            max_tokens: Maximum tokens for generated answer
        """
        self.session_manager = session_manager
        self.llm_client = llm_client
        self.default_top_k = default_top_k
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens
    
    def retrieve(
        self,
        question: str,
        session_id: str,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        """Retrieve relevant document chunks via semantic search.
        
        Args:
            question: User's question to search for
            session_id: Session identifier for isolated retrieval
            top_k: Number of chunks to retrieve (defaults to pipeline default)
            
        Returns:
            List of retrieved chunks with metadata:
                - id: Chunk identifier
                - document: Chunk text content
                - metadata: Dict with source, chunk_index, position, timestamp, etc.
                - distance: Semantic similarity distance
                
        Raises:
            ValueError: If question is empty or session not found
            
        Examples:
            >>> chunks = pipeline.retrieve("What is my job title?", "session_123")
            >>> print(chunks[0]["metadata"]["source"])
            'employment_contract.pdf'
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        # Get session's vector store
        store = self.session_manager.get_vector_store(session_id)
        if store is None:
            raise ValueError(f"Session not found or expired: {session_id}")
        
        # Perform semantic search
        top_k = top_k or self.default_top_k
        results = store.query(query_text=question, n_results=top_k)
        
        return results
    
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[dict],
        temperature: Optional[float] = None,
    ) -> str:
        """Generate answer from retrieved document chunks using LLM.
        
        Args:
            question: User's question
            retrieved_chunks: List of retrieved chunks from semantic search
            temperature: LLM temperature (defaults to pipeline default, 0.3-0.5)
            
        Returns:
            Generated answer text
            
        Raises:
            ValueError: If chunks are empty or question is invalid
            RuntimeError: If LLM generation fails
            
        Examples:
            >>> answer = pipeline.generate_answer(
            ...     question="What is my job title?",
            ...     retrieved_chunks=chunks
            ... )
            >>> print(answer)
            'Based on your employment contract, your job title is Senior Researcher.'
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        if not retrieved_chunks:
            raise ValueError("No chunks provided for answer generation")
        
        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            source = chunk.get("metadata", {}).get("source", "Unknown")
            text = chunk.get("document", "")
            context_parts.append(f"[{i}] From {source}:\n{text}\n")
        
        context = "\n".join(context_parts)
        
        # Construct prompt
        prompt = f"""Based on the following document excerpts, provide a concise answer to the question.

Question: {question}

Document Excerpts:
{context}

Instructions:
- Answer directly and concisely (max 3-4 sentences)
- Only use information from the provided excerpts
- Reference sources using [1], [2], etc. when relevant
- If the excerpts don't contain enough information, say so clearly

Answer:"""
        
        # Generate answer with temperature control
        temperature = temperature or self.default_temperature
        
        try:
            messages = [{"role": "user", "content": prompt}]
            
            # Temporarily override client temperature if different
            original_temp = self.llm_client.temperature
            self.llm_client.temperature = temperature
            
            try:
                answer = self.llm_client.create_completion(
                    messages=messages,
                    max_tokens=self.max_tokens,
                )
            finally:
                # Restore original temperature
                self.llm_client.temperature = original_temp
            
            if not answer or not answer.strip():
                raise RuntimeError("LLM returned empty answer")
            
            return answer.strip()
            
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {str(e)}") from e
    
    def format_citations(
        self,
        retrieved_chunks: list[dict],
        question: str,
        answer: str,
    ) -> list[Citation]:
        """Format citations from retrieved chunks with source metadata.
        
        Args:
            retrieved_chunks: List of retrieved chunks from semantic search
            question: User's question (for context)
            answer: Generated answer (for context)
            
        Returns:
            List of Citation objects with source metadata and text excerpts
            
        Examples:
            >>> citations = pipeline.format_citations(chunks, question, answer)
            >>> print(citations[0].source_id)
            'employment_contract.pdf'
            >>> print(citations[0].highlights[0])
            'Your position is Senior Researcher...'
        """
        citations = []
        
        for i, chunk in enumerate(retrieved_chunks, 1):
            metadata = chunk.get("metadata", {})
            chunk_text = chunk.get("document", "")
            
            # Extract source information
            source = metadata.get("source", "Unknown")
            chunk_id = chunk.get("id", metadata.get("id", f"chunk-{i}"))
            chunk_index = metadata.get("chunk_index", i - 1)
            
            # Calculate position
            position_start = metadata.get("position_start")
            position_end = metadata.get("position_end")
            position_percentage = metadata.get("position_percentage")
            
            # If position not in metadata, estimate from chunk index
            if position_percentage is None and "total_chunks" in metadata:
                total_chunks = metadata["total_chunks"]
                position_percentage = chunk_index / total_chunks if total_chunks > 0 else 0.0
            
            # Extract text excerpt (50-200 chars, prefer complete sentences)
            excerpt = self._extract_excerpt(chunk_text, max_length=200)
            
            # Create citation
            citation = Citation(
                id=f"cite_{i}",
                source_id=source,
                chunk_id=chunk_id,
                position_start=position_start,
                position_end=position_end,
                position_percentage=position_percentage,
                timestamp=datetime.utcnow(),
                highlights=[excerpt],
                metadata={
                    "chunk_index": chunk_index,
                    "distance": chunk.get("distance"),
                    "question": question,
                },
            )
            
            citations.append(citation)
        
        return citations
    
    def _extract_excerpt(self, text: str, max_length: int = 200) -> str:
        """Extract a meaningful excerpt from text.
        
        Args:
            text: Full text to excerpt from
            max_length: Maximum length of excerpt
            
        Returns:
            Excerpt with ellipsis if truncated
        """
        if len(text) <= max_length:
            return text
        
        # Try to break at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind(". ")
        last_newline = truncated.rfind("\n")
        
        break_point = max(last_period, last_newline)
        
        if break_point > max_length // 2:  # Only break if we're past halfway
            return truncated[:break_point + 1].strip()
        
        # Otherwise just truncate at word boundary
        last_space = truncated.rfind(" ")
        if last_space > 0:
            return truncated[:last_space].strip() + "..."
        
        return truncated + "..."
    
    def suggest_answer(
        self,
        question: str,
        session_id: str,
        top_k: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """Generate answer suggestion with citations (full RAG pipeline).
        
        This orchestrates the complete flow:
        1. Validate inputs
        2. Retrieve relevant chunks
        3. Generate answer from chunks
        4. Format citations
        
        Args:
            question: User's question
            session_id: Session identifier
            top_k: Number of chunks to retrieve (optional)
            temperature: LLM temperature (optional)
            
        Returns:
            Dictionary with:
                - answer (str): Generated answer text
                - citations (list[Citation]): List of citation objects
                - metadata (dict): Additional metadata (num_chunks, session_id, etc.)
                
        Raises:
            ValueError: If inputs are invalid or session not found
            RuntimeError: If any pipeline step fails
            
        Examples:
            >>> result = pipeline.suggest_answer(
            ...     question="What is my employment status?",
            ...     session_id="session_123"
            ... )
            >>> print(result["answer"])
            >>> print(f"Citations: {len(result['citations'])}")
        """
        # Validate inputs
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        if not session_id:
            raise ValueError("Session ID is required")
        
        # Step 1: Retrieve relevant chunks
        try:
            chunks = self.retrieve(question, session_id, top_k=top_k)
        except Exception as e:
            raise ValueError(f"Retrieval failed: {str(e)}") from e
        
        if not chunks:
            return {
                "answer": "I couldn't find any relevant information in your documents to answer this question.",
                "citations": [],
                "metadata": {
                    "session_id": session_id,
                    "num_chunks": 0,
                    "question": question,
                },
            }
        
        # Step 2: Generate answer
        try:
            answer = self.generate_answer(question, chunks, temperature=temperature)
        except Exception as e:
            raise RuntimeError(f"Answer generation failed: {str(e)}") from e
        
        # Step 3: Format citations
        try:
            citations = self.format_citations(chunks, question, answer)
        except Exception as e:
            raise RuntimeError(f"Citation formatting failed: {str(e)}") from e
        
        # Return structured result
        return {
            "answer": answer,
            "citations": citations,
            "metadata": {
                "session_id": session_id,
                "num_chunks": len(chunks),
                "question": question,
                "temperature": temperature or self.default_temperature,
                "top_k": top_k or self.default_top_k,
            },
        }
