"""
ProviderManager for multi-provider support in Threadlight.

The ProviderManager maintains provider instances and routes completion
requests to the correct provider based on model configuration.

Architecture:
    ThreadlightConfig.providers (dict) -> ProviderDefinition objects
    ModelConfig.provider_id -> references a provider
    ProviderManager -> creates/caches provider instances, routes requests

Example usage:
    # Configure providers in config
    config.providers = {
        "anthropic": ProviderDefinition(id="anthropic", type="anthropic", ...),
        "local-ollama": ProviderDefinition(id="local-ollama", type="local", ...),
    }

    # Configure models to use providers
    config.model_configs["claude-3-opus"] = ModelConfig(
        model_id="claude-3-opus",
        provider_id="anthropic",
        ...
    )
    config.model_configs["hermes-3"] = ModelConfig(
        model_id="hermes-3",
        provider_id="local-ollama",
        ...
    )

    # Use provider manager for routing
    manager = ProviderManager(config)
    response = manager.complete(model_id="claude-3-opus", messages=[...])  # -> Anthropic
    response = manager.complete(model_id="hermes-3", messages=[...])       # -> Ollama
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from threadlight.config import ThreadlightConfig, ProviderDefinition

from threadlight.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
)

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    Manages multiple inference providers and routes requests appropriately.

    The ProviderManager is the central hub for multi-provider support:
    - Maintains cached provider instances (lazy initialization)
    - Routes completion requests based on model's provider_id
    - Falls back to default provider when model doesn't specify one
    - Provides health checking across all providers
    - Handles provider lifecycle (initialization, cleanup)

    Thread Safety:
        Provider instances are created lazily on first use. Once created,
        providers are reused for subsequent requests. The manager itself
        is thread-safe for concurrent completion requests.
    """

    def __init__(self, config: 'ThreadlightConfig'):
        """
        Initialize the ProviderManager.

        Args:
            config: ThreadlightConfig containing provider definitions
        """
        self.config = config

        # Cached provider instances: provider_id -> BaseProvider
        self._providers: dict[str, BaseProvider] = {}

        # Default provider (from legacy ProviderConfig)
        self._default_provider: Optional[BaseProvider] = None

    def _get_or_create_provider(self, provider_id: str) -> BaseProvider:
        """
        Get or create a provider instance for the given ID.

        Uses lazy initialization - providers are only created when first needed.

        Args:
            provider_id: The provider ID to get/create

        Returns:
            BaseProvider instance

        Raises:
            ValueError: If provider_id not found in config
        """
        # Check cache first
        if provider_id in self._providers:
            return self._providers[provider_id]

        # Get provider definition
        provider_def = self.config.providers.get(provider_id)
        if not provider_def:
            raise ValueError(f"Provider not found: {provider_id}")

        # Create the provider instance
        provider = self._create_provider_from_definition(provider_def)

        # Cache it
        self._providers[provider_id] = provider
        logger.debug(f"Created provider instance: {provider_id}")

        return provider

    def _create_provider_from_definition(
        self,
        provider_def: 'ProviderDefinition'
    ) -> BaseProvider:
        """
        Create a BaseProvider instance from a ProviderDefinition.

        Args:
            provider_def: The provider definition

        Returns:
            Configured BaseProvider instance
        """
        # Import here to avoid circular import
        from threadlight.providers import create_provider

        # Build endpoint list for providers that support multiple endpoints
        endpoints = [
            {"url": ep.url, "name": ep.name, "priority": ep.priority}
            for ep in provider_def.endpoints
        ] if provider_def.endpoints else None

        # Get API key (from direct value or environment variable)
        api_key = provider_def.get_api_key()

        # Create the provider using the factory
        return create_provider(
            provider_type=provider_def.type,
            api_base=provider_def.api_base,
            api_key=api_key,
            model=provider_def.default_model or None,
            timeout=provider_def.timeout,
            endpoints=endpoints,
        )

    def _get_default_provider(self) -> BaseProvider:
        """
        Get the default provider (from legacy ProviderConfig).

        This is used when:
        - A model doesn't have a provider_id specified
        - No providers dict is configured (backward compatibility)

        Returns:
            BaseProvider instance
        """
        if self._default_provider is None:
            # Import here to avoid circular import
            from threadlight.providers import create_provider

            # Create from legacy ProviderConfig
            endpoints = [
                {"url": ep.url, "name": ep.name, "priority": ep.priority}
                for ep in self.config.provider.endpoints
            ] if self.config.provider.endpoints else None

            self._default_provider = create_provider(
                provider_type=self.config.provider.type,
                api_base=self.config.provider.api_base,
                api_key=self.config.provider.api_key,
                model=self.config.provider.model,
                timeout=self.config.provider.timeout,
                endpoints=endpoints,
            )
            logger.debug("Created default provider instance")

        return self._default_provider

    def get_provider_for_model(self, model_id: str, provider_id: Optional[str] = None) -> BaseProvider:
        """
        Get the appropriate provider for a given model.

        Resolution order:
        1. Explicit provider_id hint from caller (e.g. from frontend dropdown)
        2. Model's explicit provider_id from model config
        3. Default provider ID from config -> corresponding provider
        4. Legacy default provider (ProviderConfig)

        Args:
            model_id: The model identifier
            provider_id: Optional provider hint from the frontend

        Returns:
            BaseProvider instance to use for this model
        """
        # Use explicit provider hint if given
        if provider_id and provider_id in self.config.providers:
            return self._get_or_create_provider(provider_id)

        # Check if model has an explicit provider_id in model config
        model_config = self.config.model_configs.get(model_id)
        if model_config and model_config.provider_id:
            return self._get_or_create_provider(model_config.provider_id)

        # Check for default provider in providers dict
        default_provider_id = self.config.get_default_provider_id()
        if default_provider_id:
            return self._get_or_create_provider(default_provider_id)

        # Fall back to legacy default provider
        return self._get_default_provider()

    def complete(
        self,
        model_id: str,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Route a completion request to the appropriate provider.

        This is the main entry point for inference requests in multi-provider mode.

        Args:
            model_id: The model to use for completion
            messages: Conversation messages
            tools: Optional tool definitions
            **kwargs: Additional provider options (temperature, max_tokens, etc.)

        Returns:
            ProviderResponse from the appropriate provider
        """
        provider_id = kwargs.pop("provider_id", None)
        provider = self.get_provider_for_model(model_id, provider_id=provider_id)

        # Ensure model is set (may override provider's default)
        if "model" not in kwargs:
            kwargs["model"] = model_id

        return provider.complete(messages, tools=tools, **kwargs)

    def stream(
        self,
        model_id: str,
        messages: list[ProviderMessage],
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Route a streaming request to the appropriate provider.

        Args:
            model_id: The model to use for completion
            messages: Conversation messages
            **kwargs: Additional provider options

        Yields:
            Text chunks from the provider
        """
        provider = self.get_provider_for_model(model_id)

        # Ensure model is set
        if "model" not in kwargs:
            kwargs["model"] = model_id

        yield from provider.stream(messages, **kwargs)

    def health_check(self, provider_id: Optional[str] = None) -> dict[str, Any]:
        """
        Check health of one or all providers.

        Args:
            provider_id: Specific provider to check, or None for all

        Returns:
            Dictionary with health status:
            - If provider_id specified: {"provider_id": bool, ...}
            - If None: {"providers": {id: bool, ...}, "default": bool}
        """
        results: dict[str, Any] = {}

        if provider_id:
            # Check specific provider
            try:
                provider = self._get_or_create_provider(provider_id)
                results[provider_id] = provider.health_check()
            except ValueError:
                results[provider_id] = False
        else:
            # Check all providers
            provider_health: dict[str, bool] = {}

            for pid in self.config.providers.keys():
                try:
                    provider = self._get_or_create_provider(pid)
                    provider_health[pid] = provider.health_check()
                except Exception as e:
                    logger.warning(f"Health check failed for {pid}: {e}")
                    provider_health[pid] = False

            results["providers"] = provider_health

            # Also check default provider
            try:
                results["default"] = self._get_default_provider().health_check()
            except Exception as e:
                logger.warning(f"Health check failed for default provider: {e}")
                results["default"] = False

        return results

    def list_models(self, provider_id: Optional[str] = None) -> dict[str, list[str]]:
        """
        List available models from one or all providers.

        Args:
            provider_id: Specific provider to query, or None for all

        Returns:
            Dictionary mapping provider_id to list of model IDs
        """
        results: dict[str, list[str]] = {}

        provider_ids = [provider_id] if provider_id else list(self.config.providers.keys())

        for pid in provider_ids:
            try:
                provider = self._get_or_create_provider(pid)
                if hasattr(provider, 'list_models'):
                    results[pid] = provider.list_models()
                else:
                    results[pid] = []
            except Exception as e:
                logger.warning(f"Failed to list models for {pid}: {e}")
                results[pid] = []

        return results

    def invalidate_cache(self, provider_id: Optional[str] = None) -> None:
        """
        Invalidate cached provider instances.

        Use this after updating provider configuration to ensure
        new requests use the updated settings.

        Args:
            provider_id: Specific provider to invalidate, or None for all
        """
        if provider_id:
            if provider_id in self._providers:
                del self._providers[provider_id]
                logger.debug(f"Invalidated provider cache: {provider_id}")
        else:
            self._providers.clear()
            self._default_provider = None
            logger.debug("Invalidated all provider caches")

    def get_provider_info(self, provider_id: str) -> dict[str, Any]:
        """
        Get information about a specific provider.

        Args:
            provider_id: The provider ID

        Returns:
            Dictionary with provider information
        """
        provider_def = self.config.providers.get(provider_id)
        if not provider_def:
            return {"error": f"Provider not found: {provider_id}"}

        is_cached = provider_id in self._providers

        return {
            "id": provider_def.id,
            "name": provider_def.name,
            "type": provider_def.type,
            "api_base": provider_def.api_base,
            "default_model": provider_def.default_model,
            "endpoints": [ep.to_dict() for ep in provider_def.endpoints],
            "has_api_key": bool(provider_def.get_api_key()),
            "is_healthy": provider_def.is_healthy,
            "last_checked": provider_def.last_checked,
            "is_cached": is_cached,
        }

    def get_all_provider_info(self) -> list[dict[str, Any]]:
        """
        Get information about all configured providers.

        Returns:
            List of provider information dictionaries
        """
        return [
            self.get_provider_info(pid)
            for pid in self.config.providers.keys()
        ]
