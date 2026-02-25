"""Tests for file validation functions."""

import tempfile
from pathlib import Path

import pytest

from m_autofill.validation import (
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    FileValidationError,
    validate_file_or_raise,
    validate_file_size,
    validate_file_type,
    validate_file_upload,
)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "documents"


class TestValidateFileUpload:
    """Tests for validate_file_upload function."""

    def test_valid_txt_file(self):
        """Test validation passes for valid .txt file."""
        file_path = str(TEST_DATA_DIR / "sample.txt")
        is_valid, error = validate_file_upload(file_path)

        assert is_valid
        assert error == ""

    def test_valid_markdown_file(self):
        """Test validation passes for .md file."""
        file_path = str(TEST_DATA_DIR / "sample_markdown.md")
        is_valid, error = validate_file_upload(file_path)

        assert is_valid
        assert error == ""

    def test_nonexistent_file(self):
        """Test validation fails for nonexistent file."""
        is_valid, error = validate_file_upload("/nonexistent/file.txt")

        assert not is_valid
        assert "not found" in error.lower()

    def test_unsupported_extension(self):
        """Test validation fails for unsupported file type."""
        # Create temporary file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"content")
            tmp_path = tmp.name

        try:
            is_valid, error = validate_file_upload(tmp_path)

            assert not is_valid
            assert "unsupported" in error.lower()
        finally:
            Path(tmp_path).unlink()

    def test_oversized_file(self):
        """Test validation fails for oversized file."""
        # Create temporary large file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            # Write more than 50MB
            tmp.write(b"x" * (60 * 1024 * 1024))
            tmp_path = tmp.name

        try:
            is_valid, error = validate_file_upload(tmp_path, max_size_bytes=MAX_FILE_SIZE_BYTES)

            assert not is_valid
            assert "too large" in error.lower()
        finally:
            Path(tmp_path).unlink()

    def test_empty_file(self):
        """Test validation fails for empty file."""
        file_path = str(TEST_DATA_DIR / "empty.txt")
        is_valid, error = validate_file_upload(file_path)

        assert not is_valid
        assert "empty" in error.lower()

    def test_custom_size_limit(self):
        """Test validation with custom size limit."""
        file_path = str(TEST_DATA_DIR / "sample.txt")

        # Should pass with normal limit
        is_valid, _ = validate_file_upload(file_path)
        assert is_valid

        # Should fail with very small limit
        is_valid, error = validate_file_upload(file_path, max_size_bytes=10)
        assert not is_valid
        assert "too large" in error.lower()

    def test_custom_allowed_extensions(self):
        """Test validation with custom allowed extensions."""
        file_path = str(TEST_DATA_DIR / "sample.txt")

        # Should pass with .txt in allowed list
        is_valid, _ = validate_file_upload(file_path, allowed_extensions={".txt", ".pdf"})
        assert is_valid

        # Should fail with .txt not in allowed list
        is_valid, error = validate_file_upload(file_path, allowed_extensions={".pdf", ".docx"})
        assert not is_valid
        assert "unsupported" in error.lower()

    def test_directory_path_fails(self, tmp_path):
        """Test validation fails when path points to a directory, not a file."""
        is_valid, error = validate_file_upload(str(tmp_path))
        assert not is_valid
        assert "not a file" in error.lower()

    def test_unreadable_file_fails(self, tmp_path):
        """Test validation fails for a file with no read permissions."""
        file_path = tmp_path / "locked.txt"
        file_path.write_text("content")
        file_path.chmod(0o000)
        try:
            is_valid, error = validate_file_upload(str(file_path))
            assert not is_valid
            assert "not readable" in error.lower()
        finally:
            file_path.chmod(0o644)

    def test_oserror_on_stat_returns_error(self, tmp_path):
        """Test validation handles OSError during file size check."""
        from pathlib import Path
        from unittest.mock import patch

        file_path = tmp_path / "sample.txt"
        file_path.write_text("content")

        # exists() and is_file() also call Path.stat() internally, so allow
        # those calls to succeed and only raise on the explicit size check call.
        real_stat = file_path.stat()
        with patch.object(Path, "stat", side_effect=[real_stat, real_stat, OSError("disk error")]):
            is_valid, error = validate_file_upload(str(file_path))
        assert not is_valid
        assert "error reading file size" in error.lower()


class TestValidateFileType:
    """Tests for validate_file_type function."""

    def test_supported_extension(self):
        """Test supported extensions return True."""
        assert validate_file_type("test.txt")
        assert validate_file_type("test.pdf")
        assert validate_file_type("test.docx")
        assert validate_file_type("test.md")

    def test_unsupported_extension(self):
        """Test unsupported extensions return False."""
        assert not validate_file_type("test.exe")
        assert not validate_file_type("test.zip")
        assert not validate_file_type("test.jpg")

    def test_case_insensitive(self):
        """Test extension checking is case-insensitive."""
        assert validate_file_type("test.TXT")
        assert validate_file_type("test.PDF")
        assert validate_file_type("test.Docx")

    def test_custom_extensions(self):
        """Test with custom allowed extensions."""
        assert validate_file_type("test.xml", allowed_extensions={".xml"})
        assert not validate_file_type("test.txt", allowed_extensions={".xml"})


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_valid_size(self):
        """Test files within size limit return True."""
        file_path = str(TEST_DATA_DIR / "sample.txt")
        assert validate_file_size(file_path)

    def test_oversized_file(self):
        """Test oversized files return False."""
        file_path = str(TEST_DATA_DIR / "sample.txt")
        # Set very small limit
        assert not validate_file_size(file_path, max_size_bytes=10)

    def test_empty_file(self):
        """Test empty files return False."""
        file_path = str(TEST_DATA_DIR / "empty.txt")
        assert not validate_file_size(file_path)

    def test_nonexistent_file(self):
        """Test nonexistent files return False."""
        assert not validate_file_size("/nonexistent/file.txt")


class TestValidateFileOrRaise:
    """Tests for validate_file_or_raise function."""

    def test_valid_file_no_exception(self):
        """Test valid file raises no exception."""
        file_path = str(TEST_DATA_DIR / "sample.txt")

        # Should not raise
        validate_file_or_raise(file_path)

    def test_invalid_file_raises_exception(self):
        """Test invalid file raises FileValidationError."""
        with pytest.raises(FileValidationError):
            validate_file_or_raise("/nonexistent/file.txt")

    def test_unsupported_type_raises_exception(self):
        """Test unsupported file type raises exception."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"content")
            tmp_path = tmp.name

        try:
            with pytest.raises(FileValidationError) as exc_info:
                validate_file_or_raise(tmp_path)

            assert "unsupported" in str(exc_info.value).lower()
        finally:
            Path(tmp_path).unlink()

    def test_oversized_file_raises_exception(self):
        """Test oversized file raises exception."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"x" * (60 * 1024 * 1024))
            tmp_path = tmp.name

        try:
            with pytest.raises(FileValidationError) as exc_info:
                validate_file_or_raise(tmp_path)

            assert "too large" in str(exc_info.value).lower()
        finally:
            Path(tmp_path).unlink()


class TestConstants:
    """Tests for module constants."""

    def test_supported_extensions(self):
        """Test SUPPORTED_EXTENSIONS contains expected types."""
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS

    def test_max_file_size(self):
        """Test MAX_FILE_SIZE_BYTES is reasonable."""
        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024  # 50MB


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
