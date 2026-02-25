"""RAG (Retrieval-Augmented Generation) pipeline for answer suggestions with citations.

This module orchestrates the complete RAG flow:
1. Semantic retrieval from ChromaDB (session-scoped)
2. LLM-based answer generation from retrieved passages
3. Citation formatting with source metadata and text excerpts

All operations are session-isolated to ensure user privacy and data separation.
"""

from datetime import datetime

from m_shared.llm import LLMClient
from m_shared.models.citation import Citation
from m_shared.models.question import QuestionType
from m_shared.session import SessionManager
from m_shared.utils import AuditLogger


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
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize RAG pipeline.
        
        Args:
            session_manager: Session manager for accessing vector stores
            llm_client: LLM client for answer generation
            default_top_k: Default number of chunks to retrieve
            default_temperature: Temperature for LLM generation (0.3-0.5 for determinism)
            max_tokens: Maximum tokens for generated answer
            audit_logger: Optional audit logger for tracking suggestions
        """
        self.session_manager = session_manager
        self.llm_client = llm_client
        self.default_top_k = default_top_k
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens
        self.audit_logger = audit_logger
    
    def retrieve(
        self,
        question: str,
        session_id: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """Retrieve relevant document chunks via semantic search.

        Args:
            question: User's question to search for
            session_id: Session identifier for isolated retrieval
            top_k: Number of chunks to retrieve (defaults to pipeline default)
            filters: Optional metadata filters passed to ``query_with_filter``.
                Supported keys:
                - ``source``: str or list[str] — restrict to specific document(s)
                - ``ingested_at``: ChromaDB where-clause dict for time-range filtering,
                  e.g. ``{"$gte": 1735689600.0}`` (Unix timestamp float, as stored by ingest)

        Returns:
            List of retrieved chunks with metadata:
                - id: Chunk identifier
                - document: Chunk text content
                - metadata: Dict with source, chunk_index, ingested_at, etc.
                - distance: Semantic similarity distance

        Raises:
            ValueError: If question is empty or session not found

        Examples:
            >>> chunks = pipeline.retrieve("What is my job title?", "session_123")
            >>> chunks = pipeline.retrieve(
            ...     "What is my salary?", "session_123",
            ...     filters={"source": "contract.pdf"},
            ... )
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        store = self.session_manager.get_vector_store(session_id)
        if store is None:
            raise ValueError(f"Session not found or expired: {session_id}")

        top_k = top_k or self.default_top_k

        if filters:
            return store.query_with_filter(query_text=question, filters=filters, n_results=top_k)
        return store.query(query_text=question, n_results=top_k)
    
    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[dict],
        temperature: float | None = None,
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
    
    def _generate_answer_with_reasoning(
        self,
        question: str,
        retrieved_chunks: list[dict],
        temperature: float | None = None,
        section_context: str | None = None,
        sibling_prompts: list[str] | None = None,
        choices: list | None = None,
        question_type: str | None = None,
    ) -> tuple[str, str | None]:
        """Generate answer and reasoning from retrieved chunks using LLM.

        Uses a structured ANSWER/REASONING prompt so both fields are returned
        in a single LLM call. For choice questions also returns SELECTED.

        Args:
            question: User's question
            retrieved_chunks: Retrieved chunks from semantic search
            temperature: LLM temperature
            section_context: Optional section title for additional context
            sibling_prompts: Other question prompts in same section
            choices: List of BatchChoice objects for choice-type questions
            question_type: QuestionType value string

        Returns:
            Tuple of (answer, reasoning) — reasoning is None if not needed
        """
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            source = chunk.get("metadata", {}).get("source", "Unknown")
            text = chunk.get("document", "")
            context_parts.append(f"[{i}] From {source}:\n{text}\n")
        context = "\n".join(context_parts)

        # Build section/sibling context block
        extra_context = ""
        if section_context:
            extra_context += f"SECTION: {section_context}\n"
        if sibling_prompts:
            related = "\n".join(f"- {p}" for p in sibling_prompts)
            extra_context += f"RELATED QUESTIONS IN THIS SECTION:\n{related}\n"

        # Build choice block for choice-type questions
        choice_block = ""
        if choices:
            choice_lines = "\n".join(f"- {c.id}: {c.label}" for c in choices)
            choice_block = f"\nAVAILABLE CHOICES:\n{choice_lines}\n"
            selected_instruction = (
                "SELECTED: <choice id from the list above, or NONE if you cannot determine>\n"
            )
        else:
            selected_instruction = ""

        prompt = f"""You are helping a respondent answer a survey question based on their uploaded documents.
{extra_context}
QUESTION: {question}{choice_block}
DOCUMENT EXCERPTS:
{context}

Instructions:
- Answer directly and concisely (max 3-4 sentences)
- Only use information from the provided excerpts
- If evidence is ambiguous or missing, say so in REASONING

Respond in exactly this format:
ANSWER: <your answer>
{selected_instruction}REASONING: <brief explanation of confidence, source interpretation, or uncertainty — leave blank if answer is straightforward>"""

        temperature = temperature or self.default_temperature
        original_temp = self.llm_client.temperature
        self.llm_client.temperature = temperature

        try:
            messages = [{"role": "user", "content": prompt}]
            raw = self.llm_client.create_completion(messages=messages, max_tokens=self.max_tokens)
        finally:
            self.llm_client.temperature = original_temp

        if not raw or not raw.strip():
            raise RuntimeError("LLM returned empty response")

        return self._parse_structured_response(raw.strip())

    def _parse_structured_response(self, raw: str) -> tuple[str, str | None, str | None]:
        """Parse ANSWER/SELECTED/REASONING from structured LLM output.

        Collects all lines belonging to each block, so multi-line answers and
        reasoning are preserved. A new block starts when a line begins with a
        known prefix (ANSWER:, SELECTED:, REASONING:).

        Args:
            raw: Raw LLM output string

        Returns:
            Tuple of (answer, reasoning, selected_raw) — reasoning and selected_raw
            are None if absent or blank. selected_raw is the bare value after
            SELECTED: before any choice validation.
        """
        PREFIXES = ("ANSWER:", "SELECTED:", "REASONING:")

        blocks: dict[str, list[str]] = {}
        current_key: str | None = None

        for line in raw.splitlines():
            matched = next((p for p in PREFIXES if line.startswith(p)), None)
            if matched:
                current_key = matched.rstrip(":")
                blocks[current_key] = [line[len(matched):].strip()]
            elif current_key is not None:
                blocks[current_key].append(line)

        def get_block(key: str) -> str | None:
            lines = blocks.get(key, [])
            value = "\n".join(lines).strip()
            return value if value else None

        answer = get_block("ANSWER") or raw
        reasoning = get_block("REASONING")

        selected_raw = get_block("SELECTED")
        if selected_raw and selected_raw.upper() == "NONE":
            selected_raw = None

        return answer, reasoning, selected_raw

    def _parse_selected_id(self, selected_raw: str | None, choices: list, multi: bool) -> tuple[str | None, list[str] | None]:
        """Validate a SELECTED value against the available choices.

        Args:
            selected_raw: Bare selected value extracted by _parse_structured_response,
                          or None if the LLM returned no selection.
            choices: List of BatchChoice objects to validate against
            multi: True for multiple_choice, False for single_choice

        Returns:
            Tuple of (selected_id, selected_ids) — only one is set based on multi
        """
        if not selected_raw:
            return None, None

        valid_ids = {c.id for c in choices}

        if multi:
            candidates = [s.strip().strip(",") for s in selected_raw.replace(",", " ").split()]
            matched = [s for s in candidates if s in valid_ids]
            return None, matched if matched else None
        else:
            return (selected_raw if selected_raw in valid_ids else None), None
    
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
        top_k: int | None = None,
        temperature: float | None = None,
        user_id: str | None = None,
        question_id: str | None = None,
    ) -> dict:
        """Generate answer suggestion with citations (full RAG pipeline).
        
        This orchestrates the complete flow:
        1. Validate inputs
        2. Retrieve relevant chunks
        3. Generate answer from chunks
        4. Format citations
        5. Log to audit trail (if logger configured)
        
        Args:
            question: User's question
            session_id: Session identifier
            top_k: Number of chunks to retrieve (optional)
            temperature: LLM temperature (optional)
            user_id: Optional user ID for audit logging
            question_id: Optional question ID for audit logging
            
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
        
        # Step 2: Generate answer with reasoning
        try:
            answer, reasoning, _ = self._generate_answer_with_reasoning(question, chunks, temperature=temperature)
        except Exception as e:
            raise RuntimeError(f"Answer generation failed: {str(e)}") from e
        
        # Step 3: Format citations
        try:
            citations = self.format_citations(chunks, question, answer)
        except Exception as e:
            raise RuntimeError(f"Citation formatting failed: {str(e)}") from e
        
        # Step 4: Log to audit trail
        if self.audit_logger:
            sources_used = [c.source_id for c in citations]
            self.audit_logger.log_suggestion(
                session_id=session_id,
                question=question,
                suggested_answer=answer,
                sources_used=sources_used,
                model=self.llm_client.model_name,
                user_id=user_id,
                question_id=question_id,
            )
        
        # Return structured result
        return {
            "answer": answer,
            "reasoning": reasoning,
            "citations": citations,
            "metadata": {
                "session_id": session_id,
                "num_chunks": len(chunks),
                "question": question,
                "temperature": temperature or self.default_temperature,
                "top_k": top_k or self.default_top_k,
            },
        }

    def suggest_batch(
        self,
        sections: list,
        session_id: str,
        assessment_id: str,
        user_id: str | None = None,
    ) -> list[dict]:
        """Generate answer suggestions for multiple questionnaire items.

        Processes items section by section, injecting sibling question prompts
        as context so the LLM can reason across related questions.

        Args:
            sections: Normalized list of BatchSuggestSection objects
            session_id: Session identifier
            assessment_id: Assessment identifier for audit logging
            user_id: Optional user ID for audit logging

        Returns:
            List of suggestion dicts, one per item, in input order

        Raises:
            ValueError: If session not found
        """
        if not session_id:
            raise ValueError("Session ID is required")

        responses = []

        for section in sections:
            sibling_prompts = [item.prompt for item in section.items]

            for item in section.items:
                # Sibling context excludes the current item's own prompt
                context_prompts = [p for p in sibling_prompts if p != item.prompt]

                chunks = self.retrieve(item.prompt, session_id)

                if not chunks:
                    responses.append({
                        "item_id": item.id,
                        "type": item.type.value,
                        "suggestion": "No relevant information found in your documents for this question.",
                        "selected_id": None,
                        "selected_ids": None,
                        "reasoning": "No document chunks matched this question. Please answer manually.",
                        "citations": [],
                    })
                    continue

                is_choice = item.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE)
                is_multi = item.type == QuestionType.MULTIPLE_CHOICE
                choices = item.choices if is_choice else None

                try:
                    answer, reasoning, selected_raw = self._generate_answer_with_reasoning(
                        question=item.prompt,
                        retrieved_chunks=chunks,
                        section_context=section.title,
                        sibling_prompts=context_prompts,
                        choices=choices,
                        question_type=item.type.value,
                    )
                except RuntimeError as e:
                    responses.append({
                        "item_id": item.id,
                        "type": item.type.value,
                        "suggestion": "Generation failed.",
                        "selected_id": None,
                        "selected_ids": None,
                        "reasoning": str(e),
                        "citations": [],
                    })
                    continue

                selected_id, selected_ids = None, None
                if is_choice:
                    selected_id, selected_ids = self._parse_selected_id(selected_raw, item.choices, multi=is_multi)

                citations = self.format_citations(chunks, item.prompt, answer)

                if self.audit_logger:
                    self.audit_logger.log_suggestion(
                        session_id=session_id,
                        question=item.prompt,
                        suggested_answer=answer,
                        sources_used=[c.source_id for c in citations],
                        model=self.llm_client.model_name,
                        user_id=user_id,
                        question_id=item.id,
                    )

                responses.append({
                    "item_id": item.id,
                    "type": item.type.value,
                    "suggestion": answer,
                    "selected_id": selected_id,
                    "selected_ids": selected_ids,
                    "reasoning": reasoning,
                    "citations": citations,
                })

        return responses
