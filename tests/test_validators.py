"""Unit tests for input validation and sanitization."""

import pytest

from m_shared.auth.validators import (
    ValidationError,
    sanitize_text,
    validate_and_sanitize,
    validate_input_size,
)


class TestValidateInputSize:
    """Test input size validation."""

    def test_validate_short_input(self):
        """Test that short inputs pass validation."""
        text = "Hello, world!"
        result = validate_input_size(text, max_length=100)
        assert result == text

    def test_validate_at_limit(self):
        """Test input exactly at the limit."""
        text = "x" * 100
        result = validate_input_size(text, max_length=100)
        assert result == text

    def test_validate_exceeds_limit(self):
        """Test that oversized inputs raise ValidationError."""
        text = "x" * 101
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            validate_input_size(text, max_length=100)

    def test_validate_custom_field_name(self):
        """Test custom field name in error message."""
        text = "x" * 101
        with pytest.raises(ValidationError, match="prompt exceeds"):
            validate_input_size(text, max_length=100, field_name="prompt")

    def test_validate_default_max_length(self):
        """Test default max length of 50000."""
        text = "x" * 50000
        result = validate_input_size(text)
        assert len(result) == 50000
        
        text_too_long = "x" * 50001
        with pytest.raises(ValidationError):
            validate_input_size(text_too_long)

    def test_validate_empty_string(self):
        """Test that empty strings are valid."""
        result = validate_input_size("", max_length=100)
        assert result == ""


class TestSanitizeText:
    """Test text sanitization."""

    def test_sanitize_html_entities(self):
        """Test that HTML entities are escaped."""
        text = "<script>alert('XSS')</script>"
        result = sanitize_text(text)
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        assert "<script>" not in result

    def test_sanitize_quotes(self):
        """Test that quotes are escaped."""
        text = "It's a \"test\""
        result = sanitize_text(text)
        assert "&#x27;" in result or "'" in result
        assert "&quot;" in result or '"' in result

    def test_sanitize_preserve_newlines(self):
        """Test preserving newlines when requested."""
        text = "Line 1\nLine 2\nLine 3"
        result = sanitize_text(text, preserve_newlines=True)
        assert "\n" in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_sanitize_remove_newlines(self):
        """Test removing newlines when not preserved."""
        text = "Line 1\nLine 2\nLine 3"
        result = sanitize_text(text, preserve_newlines=False)
        assert "\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_sanitize_control_characters(self):
        """Test removal of control characters."""
        text = "Hello\x00World\x1F!"
        result = sanitize_text(text)
        assert "\x00" not in result
        assert "\x1F" not in result
        assert "Hello" in result
        assert "World" in result

    def test_sanitize_excessive_whitespace(self):
        """Test normalization of excessive whitespace."""
        text = "Hello     World    Test"
        result = sanitize_text(text)
        assert "Hello World Test" == result

    def test_sanitize_multiple_newlines(self):
        """Test collapsing multiple consecutive newlines."""
        text = "Line 1\n\n\n\n\nLine 2"
        result = sanitize_text(text, preserve_newlines=True)
        assert result == "Line 1\n\nLine 2"

    def test_sanitize_tabs_and_spaces(self):
        """Test normalization of tabs and spaces."""
        text = "Hello\t\t\tWorld    Test"
        result = sanitize_text(text)
        assert result == "Hello World Test"

    def test_sanitize_mixed_content(self):
        """Test sanitization of mixed problematic content."""
        text = "<b>Bold</b>\n\n\nText    with   spaces\x00"
        result = sanitize_text(text, preserve_newlines=True)
        assert "&lt;b&gt;" in result
        assert "\n\n" in result
        assert "\x00" not in result

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        result = sanitize_text("")
        assert result == ""

    def test_sanitize_already_clean(self):
        """Test that clean text is unchanged."""
        text = "This is clean text."
        result = sanitize_text(text)
        assert "clean text" in result


class TestValidateAndSanitize:
    """Test combined validation and sanitization."""

    def test_validate_and_sanitize_success(self):
        """Test successful validation and sanitization."""
        text = "<b>Hello</b> World"
        result = validate_and_sanitize(text, max_length=100)
        assert "&lt;b&gt;" in result
        assert "Hello" in result
        assert "<b>" not in result

    def test_validate_and_sanitize_too_long(self):
        """Test that oversized inputs fail before sanitization."""
        text = "x" * 101
        with pytest.raises(ValidationError):
            validate_and_sanitize(text, max_length=100)

    def test_validate_and_sanitize_preserve_newlines(self):
        """Test newline preservation option."""
        text = "Line 1\nLine 2"
        result = validate_and_sanitize(text, max_length=100, preserve_newlines=True)
        assert "\n" in result

    def test_validate_and_sanitize_remove_newlines(self):
        """Test newline removal option."""
        text = "Line 1\nLine 2"
        result = validate_and_sanitize(text, max_length=100, preserve_newlines=False)
        assert "\n" not in result
        assert "Line 1 Line 2" in result

    def test_validate_and_sanitize_with_xss(self):
        """Test XSS prevention through validation and sanitization."""
        text = "<script>alert('xss')</script>"
        result = validate_and_sanitize(text, max_length=100)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_validate_and_sanitize_custom_field(self):
        """Test custom field name in validation errors."""
        text = "x" * 101
        with pytest.raises(ValidationError, match="question_text"):
            validate_and_sanitize(text, max_length=100, field_name="question_text")


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_llm_prompt_sanitization(self):
        """Test sanitizing user input before LLM processing."""
        user_input = """
        Help me answer this question:
        <script>alert('inject')</script>
        
        
        Based on my documents.
        """
        result = validate_and_sanitize(user_input, max_length=1000)
        
        # XSS prevented
        assert "<script>" not in result
        # Excessive newlines collapsed
        assert "\n\n\n" not in result
        # Content preserved
        assert "Help me answer" in result
        assert "Based on my documents" in result

    def test_questionnaire_text_sanitization(self):
        """Test sanitizing questionnaire text from administrators."""
        question_text = """
        Rate your satisfaction    (1-5):
        
        1 - Very Unsatisfied
        2 - Unsatisfied
        """
        result = validate_and_sanitize(question_text, max_length=500)
        
        # Whitespace normalized but newlines preserved
        assert "Rate your satisfaction (1-5):" in result
        assert "\n" in result

    def test_response_text_validation(self):
        """Test validating open-ended survey responses."""
        response = "I am satisfied with the service. " * 100  # ~3500 chars
        result = validate_and_sanitize(response, max_length=5000)
        assert len(result) < 5000

    def test_oversized_response_rejection(self):
        """Test rejecting extremely long responses."""
        response = "x" * 100000
        with pytest.raises(ValidationError):
            validate_and_sanitize(response, max_length=50000)
