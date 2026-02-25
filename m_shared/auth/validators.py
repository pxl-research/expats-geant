"""Input validation and sanitization utilities."""

import html
import re


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


def validate_input_size(text: str, max_length: int = 50000, field_name: str = "input") -> str:
    """
    Validate input text size to prevent oversized payloads.

    Args:
        text: Input text to validate
        max_length: Maximum allowed length in characters
        field_name: Name of the field for error messages

    Returns:
        Original text if valid

    Raises:
        ValidationError: If text exceeds max_length

    Example:
        >>> validate_input_size("Hello", max_length=100)
        'Hello'
        >>> validate_input_size("x" * 60000)  # Raises ValidationError
    """
    if len(text) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters " f"(got {len(text)})"
        )
    return text


def sanitize_text(text: str, preserve_newlines: bool = True) -> str:
    """
    Sanitize text for safe LLM processing and prevent injection attacks.

    Performs:
    - HTML entity escaping to prevent XSS
    - Control character removal (except newlines if preserved)
    - Excessive whitespace normalization

    Args:
        text: Input text to sanitize
        preserve_newlines: If True, keep newlines; if False, replace with spaces

    Returns:
        Sanitized text safe for LLM processing

    Example:
        >>> sanitize_text("<script>alert('xss')</script>")
        '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'
        >>> sanitize_text("Hello\\n\\nWorld")
        'Hello\\n\\nWorld'
    """
    # HTML entity escape to prevent XSS
    text = html.escape(text)

    # Remove control characters except newlines (if preserved) and tabs
    if preserve_newlines:
        # Keep \n, remove other control chars
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
    else:
        # Remove all control characters including newlines
        text = re.sub(r"[\x00-\x1F\x7F]", " ", text)

    # Normalize excessive whitespace (collapse multiple spaces but preserve single newlines)
    if preserve_newlines:
        # Collapse spaces/tabs but keep single newlines
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse multiple consecutive newlines to max 2
        text = re.sub(r"\n{3,}", "\n\n", text)
    else:
        # Collapse all whitespace
        text = re.sub(r"\s+", " ", text)

    return text.strip()


def validate_and_sanitize(
    text: str, max_length: int = 50000, field_name: str = "input", preserve_newlines: bool = True
) -> str:
    """
    Convenience function combining validation and sanitization.

    Args:
        text: Input text to validate and sanitize
        max_length: Maximum allowed length
        field_name: Field name for error messages
        preserve_newlines: Whether to preserve newlines during sanitization

    Returns:
        Validated and sanitized text

    Raises:
        ValidationError: If validation fails

    Example:
        >>> validate_and_sanitize("<b>Hello</b>", max_length=100)
        '&lt;b&gt;Hello&lt;/b&gt;'
    """
    text = validate_input_size(text, max_length, field_name)
    text = sanitize_text(text, preserve_newlines)
    return text
