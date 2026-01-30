"""
Base classes for inference providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional


@dataclass
class ProviderMessage:
    """A message in a conversation."""

    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None

    # For assistant messages with tool calls
    tool_calls: Optional[list["ToolCall"]] = None

    # For tool response messages
    tool_call_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def tool_response(
        cls,
        tool_call_id: str,
        content: str,
    ) -> "ProviderMessage":
        """Create a tool response message."""
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
        )

    @classmethod
    def assistant_with_tool_calls(
        cls,
        content: str,
        tool_calls: list["ToolCall"],
    ) -> "ProviderMessage":
        """Create an assistant message with tool calls."""
        return cls(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )


@dataclass
class ToolCall:
    """A tool call from the model."""

    id: str
    name: str
    arguments: str  # JSON string of arguments

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass
class ProviderResponse:
    """Response from an inference provider."""

    content: str
    finish_reason: str = "stop"
    model: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Tool calls (if any)
    tool_calls: list[ToolCall] = field(default_factory=list)

    # Raw response for debugging
    raw: Optional[dict[str, Any]] = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class ProviderConfig:
    """Configuration for a provider."""

    api_base: str
    api_key: Optional[str] = None
    model: str = ""
    timeout: float = 60.0
    max_retries: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for inference providers.

    All providers must implement the complete() method.
    Streaming is optional.
    """

    def __init__(
        self,
        api_base: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs: Any
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model or ""
        self.timeout = timeout
        self.extra_config = kwargs

    @abstractmethod
    def complete(
        self,
        messages: list[ProviderMessage],
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Generate a completion for the given messages.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific options

        Returns:
            ProviderResponse with the generated content
        """
        pass

    def complete_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Simple text completion helper.

        Args:
            prompt: User message
            system: Optional system message
            **kwargs: Additional options

        Returns:
            Generated text content
        """
        messages = []

        if system:
            messages.append(ProviderMessage(role="system", content=system))

        messages.append(ProviderMessage(role="user", content=prompt))

        response = self.complete(messages, **kwargs)
        return response.content

    def stream(
        self,
        messages: list[ProviderMessage],
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream a completion token by token.

        Default implementation falls back to non-streaming.
        Override in subclasses for true streaming.
        """
        response = self.complete(messages, **kwargs)
        yield response.content

    def health_check(self) -> bool:
        """Check if the provider is reachable."""
        try:
            self.complete_text("Say 'ok'", max_tokens=5)
            return True
        except Exception:
            return False


# Provider registry
_provider_registry: dict[str, type[BaseProvider]] = {}


def register_provider(name: str):
    """Decorator to register a provider class."""
    def decorator(cls: type[BaseProvider]) -> type[BaseProvider]:
        _provider_registry[name] = cls
        return cls
    return decorator


def get_provider_class(name: str) -> type[BaseProvider]:
    """Get a provider class by name."""
    if name not in _provider_registry:
        raise ValueError(f"Unknown provider: {name}")
    return _provider_registry[name]
