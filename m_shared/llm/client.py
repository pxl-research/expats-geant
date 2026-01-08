"""
Unified LLM client abstraction supporting OpenRouter, OpenAI-compatible APIs, and local LLMs.
"""

from typing import Iterable, Optional

from openai import OpenAI


class LLMClient(OpenAI):
    """
    Client for LLM API interactions, primarily OpenRouter with fallback to OpenAI-compatible endpoints.
    Supports streaming completions, tool calling, and customizable model selection.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model_name: str = "anthropic/claude-haiku-4.5",
        tools_list: Optional[Iterable] = None,
        temperature: float = 0.7,
        custom_headers: Optional[dict] = None,
    ):
        """
        Initialize LLM client.

        Args:
            api_key: API key for the LLM service
            base_url: Base URL for the API endpoint (default: OpenRouter)
            model_name: Model identifier (e.g., 'anthropic/claude-haiku-4.5', 'mistral/mixtral-8x7b')
            tools_list: Optional list of tool definitions for function calling
            temperature: Sampling temperature (0.0-2.0); lower = deterministic, higher = creative
            custom_headers: Custom headers to include in API requests
        """
        super().__init__(base_url=base_url, api_key=api_key)

        if custom_headers is None:
            custom_headers = {
                "HTTP-Referer": "https://pxl-research.be/expats",
                "X-Title": "PXL Expats-GEANT",
            }

        self.model_name: str = model_name
        self.tools_list: Optional[Iterable] = tools_list
        self.temperature: float = temperature
        self.extra_headers: dict = custom_headers

    def create_completion_stream(
        self, messages: list[dict], stream: bool = True, **kwargs
    ):
        """
        Create a streaming chat completion.

        Args:
            messages: List of message dicts for the chat API
            stream: Whether to stream the response
            **kwargs: Additional arguments to pass to the completions API

        Returns:
            Streaming response from the LLM
        """
        return self.chat.completions.create(
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
        Create a non-streaming chat completion.

        Args:
            messages: List of message dicts for the chat API
            **kwargs: Additional arguments to pass to the completions API

        Returns:
            Generated response text
        """
        response = self.chat.completions.create(
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
