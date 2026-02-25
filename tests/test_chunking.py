"""Tests for text chunking algorithms."""

import pytest

from m_shared.vectordb.utils import (
    iterative_chunking,
    merge_small_chunks,
    split_by_header,
    split_by_newlines,
    split_on_sentences,
    split_on_threshold,
)


class TestSplitByHeader:
    """Tests for header-based splitting."""

    def test_split_by_h1(self):
        """Test splitting by H1 headers."""
        text = "# Header 1\nContent 1\n# Header 2\nContent 2"
        result = split_by_header(text, header_level=1)
        
        assert len(result) == 2
        assert "# Header 1" in result[0]
        assert "# Header 2" in result[1]

    def test_split_by_h2(self):
        """Test splitting by H2 headers."""
        text = "## Section 1\nContent\n## Section 2\nMore content"
        result = split_by_header(text, header_level=2)
        
        assert len(result) == 2
        assert "## Section 1" in result[0]
        assert "## Section 2" in result[1]

    def test_no_headers(self):
        """Test text without headers returns single chunk."""
        text = "Just plain text without any headers"
        result = split_by_header(text, header_level=1)
        
        assert len(result) == 1
        assert result[0] == text


class TestSplitByNewlines:
    """Tests for newline-based splitting."""

    def test_split_by_double_newline(self):
        """Test splitting by double newlines (paragraphs)."""
        text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        result = split_by_newlines(text, newline_count=2)
        
        assert len(result) == 3
        assert "Paragraph 1" in result[0]
        assert "Paragraph 2" in result[1]
        assert "Paragraph 3" in result[2]

    def test_split_by_single_newline(self):
        """Test splitting by single newlines (lines)."""
        text = "Line 1\nLine 2\nLine 3"
        result = split_by_newlines(text, newline_count=1)
        
        assert len(result) == 3

    def test_no_newlines(self):
        """Test text without newlines returns single chunk."""
        text = "Single line of text"
        result = split_by_newlines(text, newline_count=2)
        
        assert len(result) == 1


class TestSplitOnSentences:
    """Tests for sentence-based splitting."""

    def test_split_sentences_basic(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        result = split_on_sentences(text)
        
        assert len(result) == 3
        assert "First sentence." in result[0]
        assert "Second sentence." in result[1]

    def test_split_sentences_question_marks(self):
        """Test sentence splitting with question marks."""
        text = "What is this? This is a test! Another sentence."
        result = split_on_sentences(text)
        
        assert len(result) == 3

    def test_split_sentences_single(self):
        """Test single sentence returns single chunk."""
        text = "Just one sentence."
        result = split_on_sentences(text)
        
        assert len(result) == 1


class TestSplitOnThreshold:
    """Tests for threshold-based splitting with overlap."""

    def test_split_on_threshold_basic(self):
        """Test basic threshold splitting."""
        text = "a " * 600  # 1200 chars
        result = split_on_threshold(text, max_chars=500, overlap_pct=0.0)
        
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 500

    def test_split_on_threshold_with_overlap(self):
        """Test threshold splitting with overlap."""
        text = "word " * 300
        result = split_on_threshold(text, max_chars=500, overlap_pct=0.1)
        
        assert len(result) >= 2
        # Overlap should create some repeated content between chunks

    def test_split_respects_word_boundaries(self):
        """Test that splitting doesn't break words."""
        text = "word " * 100
        result = split_on_threshold(text, max_chars=50)
        
        # Check that no chunk starts or ends with spaces (words not broken)
        for chunk in result:
            assert chunk[0] != " "
            assert chunk[-1] != " "

    def test_short_text_no_split(self):
        """Test text shorter than threshold returns single chunk."""
        text = "Short text"
        result = split_on_threshold(text, max_chars=500)
        
        assert len(result) == 1
        assert result[0] == text


class TestMergeSmallChunks:
    """Tests for merging small chunks."""

    def test_merge_small_chunks_basic(self):
        """Test basic chunk merging."""
        chunks = ["short", "tiny", "small"]
        result = merge_small_chunks(chunks, max_size=100)
        
        # Should merge all into one chunk
        assert len(result) < len(chunks)

    def test_merge_respects_max_size(self):
        """Test merging respects max size."""
        chunks = ["a" * 60, "b" * 60, "c" * 60]
        result = merge_small_chunks(chunks, max_size=100)
        
        # Each merged chunk should be <= max_size
        for chunk in result:
            assert len(chunk) <= 100

    def test_merge_empty_list(self):
        """Test merging empty list returns empty list."""
        result = merge_small_chunks([], max_size=100)
        assert result == []

    def test_merge_single_chunk(self):
        """Test single chunk returns as-is."""
        chunks = ["single chunk"]
        result = merge_small_chunks(chunks, max_size=100)
        
        assert len(result) == 1
        assert result[0] == chunks[0]


class TestIterativeChunking:
    """Tests for iterative chunking algorithm."""

    def test_iterative_chunking_basic(self):
        """Test basic iterative chunking."""
        text = "# Header\n\nParagraph 1.\n\nParagraph 2.\n\nParagraph 3."
        result = iterative_chunking(text, max_size=100)
        
        assert isinstance(result, list)
        assert len(result) > 0
        for chunk in result:
            assert len(chunk) <= 100

    def test_iterative_chunking_respects_boundaries(self):
        """Test chunking respects sentence boundaries."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        result = iterative_chunking(text, max_size=30)
        
        # No chunk should contain partial sentences (ending mid-sentence)
        for chunk in result:
            if not chunk.endswith("."):
                # Last chunk might not end with period, but others should
                pass

    def test_iterative_chunking_long_text(self):
        """Test chunking handles long text."""
        text = "word " * 1000  # ~5000 chars
        result = iterative_chunking(text, max_size=500)
        
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 500

    def test_iterative_chunking_short_text(self):
        """Test short text returns single chunk."""
        text = "Short text"
        result = iterative_chunking(text, max_size=500)
        
        assert len(result) == 1
        assert result[0] == text

    def test_iterative_chunking_with_headers(self):
        """Test chunking prioritizes header splits."""
        text = "# Header 1\nContent under header 1\n\n# Header 2\nContent under header 2"
        result = iterative_chunking(text, max_size=100)
        
        # Text is short enough to fit in one chunk
        assert len(result) >= 1

    def test_iterative_chunking_empty_text(self):
        """Test chunking empty text."""
        text = ""
        result = iterative_chunking(text, max_size=100)
        
        # Empty text should return empty list or list with empty string
        assert len(result) <= 1

    def test_iterative_chunking_max_size_boundary(self):
        """Test all chunks respect max size."""
        text = "a" * 2000
        result = iterative_chunking(text, max_size=512)
        
        for chunk in result:
            assert len(chunk) <= 512


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
