"""
Unified LLM client abstraction supporting OpenRouter, OpenAI-compatible APIs, and local LLMs.
"""

import os
import time
from collections.abc import Iterable

import tiktoken
from openai import APIError, OpenAI, RateLimitError


class LLMClient(OpenAI):
    """
    Client for LLM API interactions, primarily OpenRouter with fallback to OpenAI-compatible endpoints.
    Supports streaming completions, tool calling, and customizable model selection.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        tools_list: Iterable | None = None,
        temperature: float = 0.7,
        custom_headers: dict | None = None,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        thinking_budget: int | None = None,
    ):
        """
        Initialize LLM client.

        Args:
            api_key: API key for the LLM service (defaults to OPENROUTER_API_KEY env var)
            base_url: Base URL for the API endpoint (defaults to OpenRouter)
            model_name: Model identifier (defaults to DEFAULT_LLM_MODEL env var)
            tools_list: Optional list of tool definitions for function calling
            temperature: Sampling temperature (0.0-2.0); lower = deterministic, higher = creative
            custom_headers: Custom headers to include in API requests
            max_retries: Maximum number of retries for rate limit/transient errors
            retry_backoff_factor: Exponential backoff multiplier for retries
            thinking_budget: Token budget for extended thinking (Claude 3.5+/4.x only).
                Overrides THINKING_BUDGET_TOKENS env var. Leave None to disable.
        """
        # Load from environment if not provided
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "API key must be provided or set in OPENROUTER_API_KEY environment variable"
            )

        base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model_name = (
            model_name
            or os.getenv("DEFAULT_LLM_MODEL", "anthropic/claude-haiku-4.5")
            or "anthropic/claude-haiku-4.5"
        )

        super().__init__(base_url=base_url, api_key=api_key)

        if custom_headers is None:
            custom_headers = {
                "HTTP-Referer": "https://pxl-research.be/expats",
                "X-Title": "PXL Expats-GEANT",
            }

        budget_env = os.getenv("THINKING_BUDGET_TOKENS")
        self.model_name: str = model_name
        self.tools_list: Iterable | None = tools_list
        self.temperature: float = temperature
        self.extra_headers: dict = custom_headers
        self.max_retries: int = max_retries
        self.retry_backoff_factor: float = retry_backoff_factor
        self.thinking_budget: int | None = thinking_budget or (
            int(budget_env) if budget_env else None
        )
        self._tokenizer = None  # Lazy load tokenizer

    def _inject_thinking(self, kwargs: dict) -> dict:
        """Inject extended-thinking config into extra_body if thinking_budget is set."""
        if self.thinking_budget is not None:
            extra_body = kwargs.get("extra_body", {})
            extra_body.setdefault(
                "thinking", {"type": "enabled", "budget_tokens": self.thinking_budget}
            )
            kwargs["extra_body"] = extra_body
        return kwargs

    def create_completion_stream(self, messages: list[dict], stream: bool = True, **kwargs):
        """
        Create a streaming chat completion with automatic retries.

        Args:
            messages: List of message dicts for the chat API
            stream: Whether to stream the response
            **kwargs: Additional arguments to pass to the completions API

        Returns:
            Streaming response from the LLM
        """
        kwargs = self._inject_thinking(kwargs)
        return self._retry_with_backoff(
            self.chat.completions.create,
            model=self.model_name,
            messages=messages,
            tools=self.tools_list,
            stream=stream,
            temperature=self.temperature,
            extra_headers=self.extra_headers,
            **kwargs,
        )

    def create_completion(self, messages: list[dict], **kwargs) -> str:
        """
        Create a non-streaming chat completion with automatic retries.

        Args:
            messages: List of message dicts for the chat API
            **kwargs: Additional arguments to pass to the completions API

        Returns:
            Generated response text
        """
        kwargs = self._inject_thinking(kwargs)
        response = self._retry_with_backoff(
            self.chat.completions.create,
            model=self.model_name,
            messages=messages,
            tools=self.tools_list,
            stream=False,
            temperature=self.temperature,
            extra_headers=self.extra_headers,
            **kwargs,
        )
        return response.choices[0].message.content

    def set_model(self, model_name: str) -> None:
        """
        Change the model for subsequent completions.

        Args:
            model_name: New model identifier
        """
        self.model_name = model_name

    def set_temperature(self, temperature: float) -> None:
        """
        Change the sampling temperature.

        Args:
            temperature: New temperature value (0.0-2.0)
        """
        self.temperature = temperature

    def _get_tokenizer(self):
        """Lazy load tokenizer for token counting."""
        if self._tokenizer is None:
            # Use cl100k_base encoding (GPT-4, GPT-3.5-turbo)
            # This is a reasonable approximation for most models
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # Fallback to basic encoding if cl100k_base not available
                self._tokenizer = tiktoken.get_encoding("gpt2")
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        tokenizer = self._get_tokenizer()
        return len(tokenizer.encode(text))

    def _retry_with_backoff(self, fn, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic.

        Args:
            fn: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return fn(*args, **kwargs)
            except RateLimitError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff_factor**attempt
                    time.sleep(wait_time)
                    continue
                raise
            except APIError as e:
                # Only retry on 5xx errors (server errors)
                if e.status_code and 500 <= e.status_code < 600:
                    last_exception = e
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_backoff_factor**attempt
                        time.sleep(wait_time)
                        continue
                raise
            except Exception:
                # Don't retry on other exceptions
                raise

        # If we exhausted all retries
        if last_exception:
            raise last_exception
