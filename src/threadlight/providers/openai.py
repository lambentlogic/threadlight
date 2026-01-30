"""
OpenAI-compatible provider for Threadlight.

Works with:
- OpenAI API
- Nous Research (Hermes)
- Local models with OpenAI-compatible endpoints (Ollama, llama.cpp, vLLM)
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

import httpx

from threadlight.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    ToolCall,
    register_provider,
)


@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_base: str = "https://inference-api.nousresearch.com/v1",
        api_key: Optional[str] = None,
        model: Optional[str] = "Hermes-4.3-36B",
        timeout: float = 60.0,
        **kwargs: Any
    ):
        super().__init__(api_base, api_key, model, timeout, **kwargs)

        # Default headers
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion using the OpenAI chat API.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions in OpenAI format
            tool_choice: Control tool usage ("auto", "none", or specific tool)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
        url = f"{self.api_base}/chat/completions"

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

        # Optional parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "presence_penalty" in kwargs:
            payload["presence_penalty"] = kwargs["presence_penalty"]
        if "frequency_penalty" in kwargs:
            payload["frequency_penalty"] = kwargs["frequency_penalty"]

        # Make request
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        # Parse response
        choice = data["choices"][0]
        message = choice["message"]
        usage = data.get("usage", {})

        # Parse tool calls if present
        tool_calls = []
        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ))

        return ProviderResponse(
            content=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            tool_calls=tool_calls,
            raw=data,
        )

    def stream(
        self,
        messages: list[ProviderMessage],
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream a completion token by token."""
        url = f"{self.api_base}/chat/completions"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }

        # Optional parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                url,
                json=payload,
                headers=self.headers
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        import json
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    def list_models(self) -> list[str]:
        """List available models."""
        url = f"{self.api_base}/models"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        return [m["id"] for m in data.get("data", [])]


# Convenience alias
NousProvider = OpenAIProvider
