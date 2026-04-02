"""File validation utilities for document ingestion.

Re-exports from m_shared.utils.file_validation for backwards compatibility.
"""

from m_shared.utils.file_validation import (  # noqa: F401
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    FileValidationError,
    validate_file_or_raise,
    validate_file_size,
    validate_file_type,
    validate_file_upload,
)
