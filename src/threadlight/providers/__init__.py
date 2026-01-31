"""
Inference providers for Threadlight.

Supports multiple backends through a unified interface:
- OpenAI-compatible APIs (OpenAI, Nous Research Hermes, etc.)
- Local models via Ollama, llama.cpp, vLLM with OpenAI-compatible endpoints

Default configuration uses Nous Research's inference API with Hermes-4.3-36B,
which provides high-quality responses well-suited for presence-centered interaction.

Provider Interface:
- complete(): Generate a completion from messages
- stream(): Stream completion tokens
- complete_text(): Simple text completion helper
- health_check(): Verify provider connectivity
"""

from threadlight.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    ProviderConfig,
    register_provider,
    get_provider_class,
)
from threadlight.providers.openai import OpenAIProvider, NousProvider
from threadlight.providers.manager import ProviderManager

__all__ = [
    # Base classes
    "BaseProvider",
    "ProviderMessage",
    "ProviderResponse",
    "ProviderConfig",
    # Registry
    "register_provider",
    "get_provider_class",
    # Implementations
    "OpenAIProvider",
    "NousProvider",  # Alias for OpenAIProvider configured for Nous
    # Factory
    "create_provider",
    # Manager
    "ProviderManager",
]

# Default API configuration
DEFAULT_API_BASE = "https://inference-api.nousresearch.com/v1"
DEFAULT_MODEL = "Hermes-4.3-36B"


def create_provider(
    provider_type: str = "openai",
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    **kwargs
) -> BaseProvider:
    """
    Factory function to create an inference provider.

    Args:
        provider_type: The provider type ("openai", "nous", or "local")
        api_base: The API base URL (defaults to Nous Research)
        api_key: The API key for authentication
        model: The model to use (defaults to Hermes-4.3-36B)
        **kwargs: Additional provider configuration

    Returns:
        A configured BaseProvider instance

    Raises:
        ValueError: If provider type is not recognized

    Example:
        # Create Nous Research provider (default)
        provider = create_provider(
            api_key="your-api-key"
        )

        # Create OpenAI provider
        provider = create_provider(
            provider_type="openai",
            api_base="https://api.openai.com/v1",
            api_key="your-openai-key",
            model="gpt-4"
        )

        # Create local provider (Ollama, etc.)
        provider = create_provider(
            provider_type="local",
            api_base="http://localhost:11434/v1",
            model="llama2"
        )
    """
    providers = {
        "openai": OpenAIProvider,
        "local": OpenAIProvider,  # Local models often use OpenAI-compatible API
        "nous": OpenAIProvider,   # Nous Research uses OpenAI-compatible API
    }

    if provider_type not in providers:
        raise ValueError(
            f"Unknown provider type: {provider_type}. "
            f"Available: {list(providers.keys())}"
        )

    # Apply defaults
    if api_base is None:
        api_base = DEFAULT_API_BASE
    if model is None:
        model = DEFAULT_MODEL

    return providers[provider_type](
        api_base=api_base,
        api_key=api_key,
        model=model,
        **kwargs
    )
