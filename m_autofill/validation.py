"""File validation utilities for document ingestion."""

import os
from pathlib import Path

# Supported file types
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".md"}

# Maximum file size in bytes (default 50MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def validate_file_upload(
    file_path: str,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    allowed_extensions: set = SUPPORTED_EXTENSIONS,
) -> tuple[bool, str]:
    """
    Validate file for upload.

    Checks:
    - File exists and is readable
    - File extension is supported
    - File size is within limits

    Args:
        file_path: Path to the file to validate
        max_size_bytes: Maximum allowed file size in bytes
        allowed_extensions: Set of allowed file extensions (including dot)

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, "")
        - If invalid: (False, "error description")
    """
    path = Path(file_path)

    # Check existence
    if not path.exists():
        return False, f"File not found: {file_path}"

    # Check if it's a file (not directory)
    if not path.is_file():
        return False, f"Path is not a file: {file_path}"

    # Check readability
    if not os.access(file_path, os.R_OK):
        return False, f"File is not readable: {file_path}"

    # Check extension
    extension = path.suffix.lower()
    if extension not in allowed_extensions:
        allowed_str = ", ".join(sorted(allowed_extensions))
        return False, f"Unsupported file type '{extension}'. Allowed: {allowed_str}"

    # Check file size
    try:
        file_size = path.stat().st_size
        if file_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return False, f"File too large: {actual_mb:.2f}MB (max: {max_mb:.0f}MB)"

        if file_size == 0:
            return False, "File is empty"

    except OSError as e:
        return False, f"Error reading file size: {str(e)}"

    return True, ""


def validate_file_type(file_path: str, allowed_extensions: set = SUPPORTED_EXTENSIONS) -> bool:
    """
    Check if file extension is supported.

    Args:
        file_path: Path to the file
        allowed_extensions: Set of allowed extensions (including dot)

    Returns:
        True if extension is supported, False otherwise
    """
    extension = Path(file_path).suffix.lower()
    return extension in allowed_extensions


def validate_file_size(file_path: str, max_size_bytes: int = MAX_FILE_SIZE_BYTES) -> bool:
    """
    Check if file size is within limits.

    Args:
        file_path: Path to the file
        max_size_bytes: Maximum allowed size in bytes

    Returns:
        True if size is acceptable, False otherwise
    """
    try:
        file_size = Path(file_path).stat().st_size
        return 0 < file_size <= max_size_bytes
    except OSError:
        return False


class FileValidationError(Exception):
    """Raised when file validation fails."""

    pass


def validate_file_or_raise(
    file_path: str,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    allowed_extensions: set = SUPPORTED_EXTENSIONS,
) -> None:
    """
    Validate file and raise exception if invalid.

    Args:
        file_path: Path to validate
        max_size_bytes: Maximum file size
        allowed_extensions: Allowed file extensions

    Raises:
        FileValidationError: If validation fails
    """
    is_valid, error_message = validate_file_upload(
        file_path, max_size_bytes=max_size_bytes, allowed_extensions=allowed_extensions
    )

    if not is_valid:
        raise FileValidationError(error_message)
