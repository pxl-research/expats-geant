"""Unit tests for LLM client."""

import os
from unittest.mock import MagicMock, patch

import pytest
from openai import APIError, RateLimitError

from m_shared.llm import LLMClient


class TestLLMClientInitialization:
    """Test LLMClient initialization and configuration."""

    def test_init_with_explicit_params(self):
        """Test initialization with explicit parameters."""
        client = LLMClient(
            api_key="test-key",
            base_url="https://test.api/v1",
            model_name="test-model",
            temperature=0.5,
        )
        assert client.model_name == "test-model"
        assert client.temperature == 0.5

    def test_init_with_env_vars(self):
        """Test initialization using environment variables."""
        with patch.dict(
            os.environ, {"OPENROUTER_API_KEY": "env-key", "DEFAULT_LLM_MODEL": "env-model"}
        ):
            client = LLMClient()
            assert client.model_name == "env-model"

    def test_init_without_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key must be provided"):
                LLMClient()

    def test_init_with_custom_retry_params(self):
        """Test initialization with custom retry parameters."""
        client = LLMClient(api_key="test-key", max_retries=5, retry_backoff_factor=3.0)
        assert client.max_retries == 5
        assert client.retry_backoff_factor == 3.0


class TestLLMClientConfiguration:
    """Test model and temperature configuration methods."""

    def test_set_model(self):
        """Test changing model after initialization."""
        client = LLMClient(api_key="test-key", model_name="model-1")
        assert client.model_name == "model-1"

        client.set_model("model-2")
        assert client.model_name == "model-2"

    def test_set_temperature(self):
        """Test changing temperature after initialization."""
        client = LLMClient(api_key="test-key", temperature=0.7)
        assert client.temperature == 0.7

        client.set_temperature(0.3)
        assert client.temperature == 0.3

    def test_per_call_temperature_override(self):
        """Test that create_completion accepts a per-call temperature without mutating the client."""
        client = LLMClient(api_key="test-key", temperature=0.7)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="response"))]
        client._retry_with_backoff = MagicMock(return_value=mock_response)

        client.create_completion(messages=[{"role": "user", "content": "hi"}], temperature=0.0)

        call_kwargs = client._retry_with_backoff.call_args
        assert call_kwargs.kwargs["temperature"] == 0.0
        assert client.temperature == 0.7

    def test_default_temperature_used_when_no_override(self):
        """Test that create_completion uses client temperature when no override is passed."""
        client = LLMClient(api_key="test-key", temperature=0.5)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="response"))]
        client._retry_with_backoff = MagicMock(return_value=mock_response)

        client.create_completion(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = client._retry_with_backoff.call_args
        assert call_kwargs.kwargs["temperature"] == 0.5


class TestTokenCounting:
    """Test token counting functionality."""

    def test_count_tokens_simple_text(self):
        """Test token counting for simple text."""
        client = LLMClient(api_key="test-key")

        # Simple phrase should have reasonable token count
        count = client.count_tokens("Hello, world!")
        assert count > 0
        assert count < 10  # Should be a few tokens

    def test_count_tokens_empty_string(self):
        """Test token counting for empty string."""
        client = LLMClient(api_key="test-key")
        assert client.count_tokens("") == 0

    def test_count_tokens_longer_text(self):
        """Test token counting scales with text length."""
        client = LLMClient(api_key="test-key")

        short_text = "Hello"
        long_text = "Hello " * 100

        short_count = client.count_tokens(short_text)
        long_count = client.count_tokens(long_text)

        assert long_count > short_count
        assert long_count > short_count * 50  # Should be roughly proportional

    def test_tokenizer_lazy_loading(self):
        """Test that tokenizer is lazy loaded."""
        client = LLMClient(api_key="test-key")

        # Tokenizer should be None initially
        assert client._tokenizer is None

        # First call should load tokenizer
        client.count_tokens("test")
        assert client._tokenizer is not None

        # Subsequent calls should reuse same tokenizer
        tokenizer = client._tokenizer
        client.count_tokens("another test")
        assert client._tokenizer is tokenizer


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_successful_completion_no_retry(self):
        """Test successful completion doesn't retry."""
        client = LLMClient(api_key="test-key")

        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch.object(
            client.chat.completions, "create", return_value=mock_response
        ) as mock_create:
            result = client.create_completion([{"role": "user", "content": "test"}])

            assert result == "Test response"
            assert mock_create.call_count == 1

    def test_rate_limit_retry_success(self):
        """Test retry on rate limit error with eventual success."""
        client = LLMClient(api_key="test-key", max_retries=3, retry_backoff_factor=1.0)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Success after retry"))]

        with patch.object(client.chat.completions, "create") as mock_create:
            # First call raises RateLimitError, second succeeds
            mock_create.side_effect = [
                RateLimitError("Rate limit", response=MagicMock(status_code=429), body=None),
                mock_response,
            ]

            with patch("time.sleep") as mock_sleep:
                result = client.create_completion([{"role": "user", "content": "test"}])

                assert result == "Success after retry"
                assert mock_create.call_count == 2
                assert mock_sleep.call_count == 1  # Called once for backoff

    def test_rate_limit_exhausts_retries(self):
        """Test rate limit error exhausts all retries."""
        client = LLMClient(api_key="test-key", max_retries=2, retry_backoff_factor=1.0)

        with patch.object(client.chat.completions, "create") as mock_create:
            # Always raise RateLimitError
            mock_create.side_effect = RateLimitError(
                "Rate limit", response=MagicMock(status_code=429), body=None
            )

            with patch("time.sleep"):
                with pytest.raises(RateLimitError):
                    client.create_completion([{"role": "user", "content": "test"}])

                # Should try max_retries times
                assert mock_create.call_count == 2

    def test_server_error_retry_success(self):
        """Test retry on 5xx server error with eventual success."""
        client = LLMClient(api_key="test-key", max_retries=3, retry_backoff_factor=1.0)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Success after retry"))]

        # Create a proper APIError with status_code
        api_error = APIError("Server error", request=MagicMock(), body=None)
        api_error.status_code = 503

        with patch.object(client.chat.completions, "create") as mock_create:
            # First call raises 503, second succeeds
            mock_create.side_effect = [api_error, mock_response]

            with patch("time.sleep") as mock_sleep:
                result = client.create_completion([{"role": "user", "content": "test"}])

                assert result == "Success after retry"
                assert mock_create.call_count == 2
                assert mock_sleep.call_count == 1

    def test_client_error_no_retry(self):
        """Test 4xx client errors don't trigger retry."""
        client = LLMClient(api_key="test-key", max_retries=3)

        # Create a 400 error (client error, should not retry)
        api_error = APIError("Bad request", request=MagicMock(), body=None)
        api_error.status_code = 400

        with patch.object(client.chat.completions, "create") as mock_create:
            mock_create.side_effect = api_error

            with pytest.raises(APIError):
                client.create_completion([{"role": "user", "content": "test"}])

            # Should only try once (no retries for 4xx)
            assert mock_create.call_count == 1

    def test_exponential_backoff_timing(self):
        """Test exponential backoff increases wait time."""
        client = LLMClient(api_key="test-key", max_retries=4, retry_backoff_factor=2.0)

        with patch.object(client.chat.completions, "create") as mock_create:
            mock_create.side_effect = RateLimitError(
                "Rate limit", response=MagicMock(status_code=429), body=None
            )

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(RateLimitError):
                    client.create_completion([{"role": "user", "content": "test"}])

                # Check that sleep times follow exponential pattern
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert len(sleep_calls) == 3  # max_retries - 1

                # Should be: 2^0=1, 2^1=2, 2^2=4
                assert sleep_calls[0] == 1.0
                assert sleep_calls[1] == 2.0
                assert sleep_calls[2] == 4.0


class TestStreamingCompletion:
    """Test streaming completion with retry logic."""

    def test_streaming_completion_success(self):
        """Test successful streaming completion."""
        client = LLMClient(api_key="test-key")

        mock_stream = MagicMock()

        with patch.object(
            client.chat.completions, "create", return_value=mock_stream
        ) as mock_create:
            result = client.create_completion_stream([{"role": "user", "content": "test"}])

            assert result == mock_stream
            assert mock_create.call_count == 1
            # Verify stream=True was passed
            assert mock_create.call_args[1]["stream"] is True

    def test_streaming_completion_retry_on_error(self):
        """Test streaming completion retries on rate limit."""
        client = LLMClient(api_key="test-key", max_retries=2, retry_backoff_factor=1.0)

        mock_stream = MagicMock()

        with patch.object(client.chat.completions, "create") as mock_create:
            mock_create.side_effect = [
                RateLimitError("Rate limit", response=MagicMock(status_code=429), body=None),
                mock_stream,
            ]

            with patch("time.sleep"):
                result = client.create_completion_stream([{"role": "user", "content": "test"}])

                assert result == mock_stream
                assert mock_create.call_count == 2
