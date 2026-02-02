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
        Generate a completion using the OpenAI API.

        Automatically detects whether to use Chat Completions API, Responses API,
        or text-based tool calling based on model capabilities.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions in OpenAI format
            tool_choice: Control tool usage ("auto", "none", or specific tool)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
        model = kwargs.get("model", self.model)
        logger.info(f"[provider] complete model={model} messages={len(messages)} tools={len(tools) if tools else 0}")

        # For chatgpt-4o-latest, try Chat Completions API with native tools first
        # (Responses API doesn't work, but Chat Completions might)
        if tools and model == "chatgpt-4o-latest":
            logger.info(f"Trying Chat Completions API with native tools for {model}")
            try:
                return self._complete_with_chat_completions_api(messages, tools, tool_choice, **kwargs)
            except Exception as e:
                logger.warning(f"Native tools failed for {model}, falling back to text-based: {e}")
                return self._complete_with_text_tools(messages, tools, tool_choice, **kwargs)

        # For other chatgpt-* models with tools, try Responses API first
        if tools and model and model.startswith("chatgpt-"):
            logger.info(f"Trying Responses API for model {model} with tools")
            try:
                return self._complete_with_responses_api(messages, tools, tool_choice, **kwargs)
            except ValueError as e:
                # ValueError is raised when functions are not supported
                logger.warning(f"Model {model} doesn't support function calling, using text-based tools: {e}")
                return self._complete_with_text_tools(messages, tools, tool_choice, **kwargs)

        # Otherwise use Chat Completions API
        return self._complete_with_chat_completions_api(messages, tools, tool_choice, **kwargs)

    def _complete_with_chat_completions_api(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion using the Chat Completions API (/v1/chat/completions).

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
                # Log request details for debugging
                logger.info(f"[OpenAI] Sending request to {url}")
                logger.info(f"[OpenAI] Model: {payload.get('model')}")
                logger.info(f"[OpenAI] Has tools: {'tools' in payload}")
                if 'tools' in payload:
                    logger.info(f"[OpenAI] Tool count: {len(payload['tools'])}")

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
                # Log response body for debugging
                try:
                    error_body = e.response.json()
                    logger.error(f"[OpenAI] Error response body: {error_body}")
                except Exception:
                    logger.error(f"[OpenAI] Error response text: {e.response.text}")

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

        # Log response details for debugging tool calling
        logger.info(f"[OpenAI DEBUG] Response finish_reason: {choice.get('finish_reason')}")
        logger.info(f"[OpenAI DEBUG] Response has tool_calls: {'tool_calls' in message}")
        if 'tool_calls' in message and message['tool_calls']:
            logger.info(f"[OpenAI DEBUG] Tool calls in response: {len(message['tool_calls'])}")
            for tc in message['tool_calls']:
                logger.info(f"[OpenAI DEBUG]   Tool: {tc['function']['name']}, args: {tc['function']['arguments'][:100]}...")
        else:
            logger.info(f"[OpenAI DEBUG] No tool_calls in response, content preview: {message.get('content', '')[:200]}...")

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

    def _complete_with_responses_api(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion using the Responses API (/v1/responses).

        This API is used for chatgpt-* models and supports an agentic loop
        where the model can call multiple tools in a single request.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions in OpenAI format
            tool_choice: Control tool usage ("auto", "none", or specific tool)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
        import json as json_module

        # Convert messages to input format - exclude tool_calls as Responses API doesn't support them
        input_list = []
        for m in messages:
            msg_dict = {"role": m.role, "content": m.content}
            if m.name:
                msg_dict["name"] = m.name
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            # Note: tool_calls are NOT included - Responses API doesn't support them in input
            input_list.append(msg_dict)

        payload: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "input": input_list,
        }

        # Log full request payload
        logger.info(f"[Responses API] Full request payload: {json_module.dumps(payload, indent=2)}")

        # Add tools if provided - transform from Chat Completions format to Responses format
        if tools:
            # Responses API expects: {"type": "function", "name": "...", "description": "...", "parameters": {...}}
            # Chat Completions API uses: {"type": "function", "function": {"name": "...", ...}}
            transformed_tools = []
            for tool in tools:
                if tool.get("type") == "function" and "function" in tool:
                    # Transform from Chat Completions format
                    func = tool["function"]
                    transformed_tools.append({
                        "type": "function",
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {})
                    })
                else:
                    # Already in Responses format or unknown format
                    transformed_tools.append(tool)
            payload["tools"] = transformed_tools

        # Optional parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]

        # Try request with fallback across endpoints
        endpoints = self._get_endpoint_urls()
        last_error = None
        used_endpoint = ""

        for endpoint_url in endpoints:
            url = f"{endpoint_url}/responses"
            used_endpoint = endpoint_url

            try:
                logger.info(f"[Responses API] Sending request to {url}")
                logger.info(f"[Responses API] Model: {payload.get('model')}")
                logger.info(f"[Responses API] Tool count: {len(payload.get('tools', []))}")

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=self.headers)
                    response.raise_for_status()
                    data = response.json()

                logger.info(f"[Responses API] Request succeeded")
                break

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"Endpoint {endpoint_url} failed (connection error): {e}. Trying next...")
                continue
            except httpx.HTTPStatusError as e:
                # Log response body for debugging
                try:
                    error_body = e.response.json()
                    logger.error(f"[Responses API] Error response body: {error_body}")

                    # Check if error indicates no function calling support
                    error_msg = error_body.get("error", {}).get("message", "").lower()
                    if "functions are not supported" in error_msg or "not supported" in error_msg:
                        # Raise a specific error we can catch
                        raise ValueError(f"Functions not supported: {error_msg}") from e
                except ValueError:
                    # Re-raise our custom ValueError
                    raise
                except Exception:
                    logger.error(f"[Responses API] Error response text: {e.response.text}")

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

        # Parse Responses API response
        # The output is a list of items including text and function_call items
        output = data.get("output", [])
        usage = data.get("usage", {})

        # Extract content and tool calls from output
        content_parts = []
        tool_calls = []

        for item in output:
            if isinstance(item, dict):
                if item.get("type") == "message" and item.get("role") == "assistant":
                    # Assistant message content
                    if "content" in item:
                        content_parts.append(item["content"])
                elif item.get("type") == "function_call":
                    # Tool call
                    tool_calls.append(ToolCall(
                        id=item.get("call_id", ""),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", "{}"),
                    ))

        content = " ".join(content_parts) if content_parts else ""

        response_obj = ProviderResponse(
            content=content,
            finish_reason=data.get("stop_reason", "stop"),
            model=data.get("model", self.model),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            tool_calls=tool_calls,
            raw=data,
        )

        # Add endpoint info to raw data for debugging
        if response_obj.raw:
            response_obj.raw["_endpoint_used"] = used_endpoint
            response_obj.raw["_api_type"] = "responses"

        return response_obj

    def _complete_with_text_tools(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict[str, Any]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion using text-based tool calling (XML format in prompt).

        This is a fallback for models that don't support native function calling.
        Tools are described in XML format in the system prompt, and the model's
        response is parsed for XML tool call patterns.

        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions in OpenAI format
            tool_choice: Control tool usage ("auto", "none", or specific tool)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse with content and/or tool_calls
        """
        import json as json_module
        import re

        # Build tool documentation in XML format
        tool_docs = self._format_tools_as_xml(tools)
        logger.info(f"[Text Tools] Added {len(tools)} tools to system prompt in XML format")

        # Inject tool docs into system message and convert tool messages to user messages
        modified_messages = []
        system_injected = False

        for msg in messages:
            if msg.role == "system" and not system_injected:
                # Add tool docs to existing system message
                modified_messages.append(ProviderMessage(
                    role="system",
                    content=msg.content + "\n\n" + tool_docs
                ))
                system_injected = True
            elif msg.role == "tool":
                # Convert tool result messages to user messages for models without function calling
                modified_messages.append(ProviderMessage(
                    role="user",
                    content=f"Tool result: {msg.content}"
                ))
            elif msg.role == "assistant" and msg.tool_calls:
                # Strip tool_calls from assistant messages - we're using text-based calling
                modified_messages.append(ProviderMessage(
                    role="assistant",
                    content=msg.content
                ))
            else:
                modified_messages.append(msg)

        # If no system message, add one with just tool docs
        if not system_injected:
            modified_messages.insert(0, ProviderMessage(role="system", content=tool_docs))

        # Log full conversation for debugging
        logger.info(f"[Text Tools] === FULL CONVERSATION ({len(modified_messages)} messages) ===")
        for i, msg in enumerate(modified_messages):
            logger.info(f"[Text Tools] [{i}] {msg.role}:")
            logger.info(f"{msg.content}")
            logger.info(f"[Text Tools] --- end message {i} ---")
        logger.info(f"[Text Tools] === END CONVERSATION ===")

        # Call model without function calling (use Chat Completions API)
        kwargs_copy = kwargs.copy()
        kwargs_copy.pop("model", None)  # Remove to avoid duplication

        # Set a reasonable max_tokens if not specified (default is too low)
        if "max_tokens" not in kwargs_copy:
            kwargs_copy["max_tokens"] = 16384

        response = self._complete_with_chat_completions_api(
            modified_messages,
            tools=None,  # Don't pass tools to avoid function calling attempt
            tool_choice=None,
            model=kwargs.get("model", self.model),
            **kwargs_copy
        )

        # Parse response for tool calls in XML format
        logger.info(f"[Text Tools] === FULL RESPONSE ===")
        logger.info(f"[Text Tools] {response.content}")
        logger.info(f"[Text Tools] === END RESPONSE ===")

        tool_calls = self._parse_xml_tool_calls(response.content)

        if tool_calls:
            logger.info(f"[Text Tools] Parsed {len(tool_calls)} tool call(s) from response")
            for tc in tool_calls:
                logger.info(f"[Text Tools] Tool call: {tc.name} with args: {tc.arguments[:100]}")
            response.tool_calls = tool_calls
        else:
            logger.warning(f"[Text Tools] No tool calls found in response")

        return response

    def _format_tools_as_xml(self, tools: Optional[list[dict[str, Any]]]) -> str:
        """Format tool definitions as XML for text-based tool calling."""
        if not tools:
            return ""

        xml_parts = [
            "# Available Tools",
            "",
            "You have access to the following tools. To use a tool, you MUST include the XML block in your response.",
            "IMPORTANT: Do not just describe what you will do - actually include the <tool_call> block.",
            "",
            "Format:",
            "<tool_call>",
            "<name>tool_name</name>",
            "<arguments>{\"param\": \"value\"}</arguments>",
            "</tool_call>",
            "",
            "You may include brief text before or after the tool call. Arguments must be valid JSON.",
            "",
            "Tools:",
            ""
        ]

        for tool in tools:
            if tool.get("type") == "function":
                if "function" in tool:
                    # Chat Completions format
                    func = tool["function"]
                else:
                    # Responses format (already flat)
                    func = tool

                xml_parts.append(f"\n<tool name=\"{func['name']}\">")
                xml_parts.append(f"  <description>{func.get('description', '')}</description>")

                params = func.get("parameters", {})
                if params and "properties" in params:
                    xml_parts.append("  <parameters>")
                    for param_name, param_def in params["properties"].items():
                        required = param_name in params.get("required", [])
                        xml_parts.append(f"    <parameter name=\"{param_name}\" required=\"{required}\">")
                        xml_parts.append(f"      <type>{param_def.get('type', 'string')}</type>")
                        if "description" in param_def:
                            xml_parts.append(f"      <description>{param_def['description']}</description>")
                        if "enum" in param_def:
                            xml_parts.append(f"      <enum>{', '.join(param_def['enum'])}</enum>")
                        xml_parts.append(f"    </parameter>")
                    xml_parts.append("  </parameters>")

                xml_parts.append("</tool>")

        return "\n".join(xml_parts)

    def _parse_xml_tool_calls(self, text: str) -> list[ToolCall]:
        """Parse XML-formatted tool calls from model response."""
        import re
        import json as json_module
        import uuid

        tool_calls = []

        # Find all <tool_call>...</tool_call> blocks
        pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            # Extract name
            name_match = re.search(r'<name>(.*?)</name>', match, re.DOTALL)
            if not name_match:
                continue
            name = name_match.group(1).strip()

            # Extract arguments
            args_match = re.search(r'<arguments>(.*?)</arguments>', match, re.DOTALL)
            arguments = args_match.group(1).strip() if args_match else "{}"

            # Create tool call
            tool_calls.append(ToolCall(
                id=f"text_tool_{uuid.uuid4().hex[:8]}",
                name=name,
                arguments=arguments,
            ))

        return tool_calls

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
