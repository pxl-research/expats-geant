"""Tests for document ingestion pipeline."""

import os
from pathlib import Path

import pytest

from m_shared.vectordb.utils import (
    clean_up_string,
    document_to_markdown,
    sanitize_filename,
)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


class TestTextExtraction:
    """Tests for text extraction from various document formats."""

    def test_extract_text_from_txt_file(self):
        """Test extraction from plain text file."""
        file_path = str(TEST_DATA_DIR / "sample.txt")
        result = document_to_markdown(file_path)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "sample text document" in result.lower()
        assert "multiple paragraphs" in result.lower()

    def test_extract_text_from_markdown(self):
        """Test extraction from markdown file."""
        file_path = str(TEST_DATA_DIR / "sample_markdown.md")
        result = document_to_markdown(file_path)
        
        assert isinstance(result, str)
        assert "# Sample Document" in result
        assert "## Section 1" in result
        assert "M-Autofill" in result

    def test_extract_empty_file(self):
        """Test extraction from empty file."""
        file_path = str(TEST_DATA_DIR / "empty.txt")
        result = document_to_markdown(file_path)
        
        assert isinstance(result, str)
        assert len(result.strip()) == 0

    def test_extract_nonexistent_file(self):
        """Test extraction from nonexistent file raises error."""
        file_path = str(TEST_DATA_DIR / "nonexistent.txt")
        
        with pytest.raises(Exception):  # MarkItDown will raise an error
            document_to_markdown(file_path)


class TestFilenameSanitization:
    """Tests for filename sanitization and validation."""

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        result = sanitize_filename("/path/to/My Document.pdf")
        
        assert result == "my-document"
        assert " " not in result
        assert "/" not in result
        assert "." not in result

    def test_sanitize_filename_special_characters(self):
        """Test sanitization removes special characters."""
        result = sanitize_filename("/path/to/Doc@2024!.txt")
        
        # Special characters converted to dashes (may have trailing dash)
        assert result.startswith("doc-2024")
        assert "@" not in result
        assert "!" not in result

    def test_sanitize_filename_underscores_to_dashes(self):
        """Test underscores converted to dashes."""
        result = sanitize_filename("my_test_file.pdf")
        
        assert result == "my-test-file"
        assert "_" not in result

    def test_sanitize_filename_max_length(self):
        """Test filename truncation to max length."""
        long_name = "a" * 100 + ".txt"
        result = sanitize_filename(long_name, max_length=30)
        
        assert len(result) == 30

    def test_clean_up_string(self):
        """Test general string cleanup function."""
        result = clean_up_string("Test String 123!")
        
        assert result.startswith("test-string-123")
        assert result.islower()
        assert " " not in result


class TestFileValidation:
    """Tests for file validation (size, type, existence)."""

    def test_file_exists(self):
        """Test that sample files exist."""
        assert (TEST_DATA_DIR / "sample.txt").exists()
        assert (TEST_DATA_DIR / "sample_markdown.md").exists()

    def test_file_readable(self):
        """Test that files can be read."""
        file_path = TEST_DATA_DIR / "sample.txt"
        
        with open(file_path) as f:
            content = f.read()
            assert len(content) > 0

    def test_file_size(self):
        """Test file size detection."""
        file_path = TEST_DATA_DIR / "sample.txt"
        size = os.path.getsize(file_path)
        
        assert size > 0
        assert size < 10000  # Small test file

    def test_large_file_size(self):
        """Test large file detection."""
        file_path = TEST_DATA_DIR / "long_text.txt"
        size = os.path.getsize(file_path)
        
        assert size > 1000  # Should be a reasonable size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
