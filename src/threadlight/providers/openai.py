"""
OpenAI-compatible provider for Threadlight.

Works with:
- OpenAI API
- Nous Research (Hermes)
- Local models with OpenAI-compatible endpoints (Ollama, llama.cpp, vLLM)

Supports multiple endpoints with automatic fallback on failure.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

import httpx

from threadlight.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    ToolCall,
    register_provider,
)

logger = logging.getLogger(__name__)


@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs.

    Supports multiple endpoints with automatic fallback on failure.
    When multiple endpoints are configured, requests will be attempted
    in priority order until one succeeds.
    """

    def __init__(
        self,
        api_base: str = "https://inference-api.nousresearch.com/v1",
        api_key: Optional[str] = None,
        model: Optional[str] = "Hermes-4.3-36B",
        timeout: float = 60.0,
        endpoints: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ):
        super().__init__(api_base, api_key, model, timeout, **kwargs)

        # Multiple endpoints support
        # Each endpoint dict should have: url, name (optional), priority (optional)
        self.endpoints = endpoints or []
        if not self.endpoints and api_base:
            # Use single api_base as the only endpoint for backward compatibility
            self.endpoints = [{"url": api_base, "name": "Primary", "priority": 0}]

        # Sort endpoints by priority (lower number = higher priority)
        self.endpoints.sort(key=lambda e: e.get("priority", 0))

        # Default headers
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_endpoint_urls(self) -> list[str]:
        """Get list of endpoint URLs in priority order."""
        if self.endpoints:
            return [ep.get("url", "").rstrip("/") for ep in self.endpoints if ep.get("url")]
        return [self.api_base] if self.api_base else []

    def _try_request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> tuple[httpx.Response, str]:
        """Try request across multiple endpoints with fallback.

        Args:
            method: HTTP method ("GET" or "POST")
            path: API path (e.g., "/chat/completions")
            payload: JSON payload for POST requests
            stream: Whether to use streaming

        Returns:
            Tuple of (response, endpoint_url_used)

        Raises:
            httpx.HTTPStatusError: If all endpoints fail
        """
        endpoints = self._get_endpoint_urls()
        last_error = None
        last_endpoint = ""

        for endpoint_url in endpoints:
            url = f"{endpoint_url}{path}"
            last_endpoint = endpoint_url

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = client.get(url, headers=self.headers)
                    else:
                        if stream:
                            # For streaming, return early so caller can handle
                            return (
                                client.stream("POST", url, json=payload, headers=self.headers),
                                endpoint_url,
                            )
                        response = client.post(url, json=payload, headers=self.headers)

                    response.raise_for_status()
                    logger.debug(f"Request succeeded on endpoint: {endpoint_url}")
                    return (response, endpoint_url)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                logger.warning(f"Endpoint {endpoint_url} failed: {e}. Trying next endpoint...")
                continue

        # All endpoints failed
        if last_error:
            logger.error(f"All endpoints failed. Last error from {last_endpoint}: {last_error}")
            raise last_error

        raise httpx.HTTPStatusError(
            "No endpoints available",
            request=httpx.Request("POST", ""),
            response=httpx.Response(503),
        )

    def complete(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion using the OpenAI chat API.

        Automatically tries fallback endpoints if the primary fails.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions in OpenAI format
            tool_choice: Control tool usage ("auto", "none", or specific tool)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
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

        # Try request with fallback across endpoints
        endpoints = self._get_endpoint_urls()
        last_error = None
        used_endpoint = ""

        for endpoint_url in endpoints:
            url = f"{endpoint_url}/chat/completions"
            used_endpoint = endpoint_url

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=self.headers)
                    response.raise_for_status()
                    data = response.json()

                logger.debug(f"Completion succeeded on endpoint: {endpoint_url}")
                break

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"Endpoint {endpoint_url} failed (connection error): {e}. Trying next...")
                continue
            except httpx.HTTPStatusError as e:
                # Don't retry on authentication errors (401, 403)
                if e.response.status_code in (401, 403):
                    raise
                last_error = e
                logger.warning(f"Endpoint {endpoint_url} failed (HTTP {e.response.status_code}): {e}. Trying next...")
                continue
        else:
            # All endpoints failed
            if last_error:
                logger.error(f"All {len(endpoints)} endpoints failed. Last error: {last_error}")
                raise last_error
            raise httpx.HTTPStatusError(
                "No endpoints available",
                request=httpx.Request("POST", ""),
                response=httpx.Response(503),
            )

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

        response_obj = ProviderResponse(
            content=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            tool_calls=tool_calls,
            raw=data,
        )

        # Add endpoint info to raw data for debugging
        if response_obj.raw:
            response_obj.raw["_endpoint_used"] = used_endpoint

        return response_obj

    def stream(
        self,
        messages: list[ProviderMessage],
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream a completion token by token.

        Automatically tries fallback endpoints if the primary fails.
        """
        import json

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

        # Try endpoints with fallback
        endpoints = self._get_endpoint_urls()
        last_error = None

        for endpoint_url in endpoints:
            url = f"{endpoint_url}/chat/completions"

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    with client.stream(
                        "POST",
                        url,
                        json=payload,
                        headers=self.headers
                    ) as response:
                        response.raise_for_status()
                        logger.debug(f"Stream started on endpoint: {endpoint_url}")

                        for line in response.iter_lines():
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    break

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

                        # Stream completed successfully
                        return

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"Stream endpoint {endpoint_url} failed: {e}. Trying next...")
                continue
            except httpx.HTTPStatusError as e:
                # Don't retry on authentication errors
                if e.response.status_code in (401, 403):
                    raise
                last_error = e
                logger.warning(f"Stream endpoint {endpoint_url} failed (HTTP {e.response.status_code}). Trying next...")
                continue

        # All endpoints failed
        if last_error:
            logger.error(f"All stream endpoints failed. Last error: {last_error}")
            raise last_error

    def list_models(self) -> list[str]:
        """List available models.

        Tries endpoints in priority order until one succeeds.
        """
        endpoints = self._get_endpoint_urls()
        last_error = None

        for endpoint_url in endpoints:
            url = f"{endpoint_url}/models"

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, headers=self.headers)
                    response.raise_for_status()
                    data = response.json()

                logger.debug(f"Models listed from endpoint: {endpoint_url}")
                return [m["id"] for m in data.get("data", [])]

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"List models failed on {endpoint_url}: {e}. Trying next...")
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    raise
                last_error = e
                continue

        if last_error:
            raise last_error
        return []


# Convenience alias
NousProvider = OpenAIProvider
