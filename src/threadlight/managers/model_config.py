"""
Model configuration management for Threadlight.

This module handles model-specific configuration including:
- Switching between models with different settings
- Creating, updating, and deleting model configurations
- Managing config auto-save
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.config import ModelConfig

logger = logging.getLogger(__name__)


class ModelConfigManager:
    """
    Manages model configuration operations for Threadlight.

    This manager handles:
    - Switching between models
    - Applying model-specific settings
    - CRUD operations for model configurations
    - Config auto-save management
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the model config manager.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def switch(self, model_id: str) -> 'ModelConfig':
        """
        Switch to a different model and load its config.

        This will:
        1. Save the current model's config if it changed
        2. Update the current model
        3. Load the new model's config
        4. Apply model-specific settings
        5. Update memory orchestrator's current model (for per-model isolation)

        Args:
            model_id: Model identifier to switch to

        Returns:
            The ModelConfig for the new model
        """
        # Update current model
        self.tl.config.current_model = model_id
        self.tl.config.provider.model = model_id

        # Get model config (creates default if not exists)
        model_config = self.tl.config.get_model_config(model_id)

        # Apply model-specific settings
        self.apply(model_config)

        # Update provider model
        self.tl.provider.model = model_id

        # Update memory orchestrator's current model (for per-model isolation)
        self.tl.memory.current_model = model_id

        # Trigger auto-save if enabled
        self.tl.config.mark_changed()

        logger.info(f"Switched to model: {model_id}")
        return model_config

    def apply(self, model_config: 'ModelConfig') -> None:
        """
        Apply a model config to the current state.

        Args:
            model_config: The ModelConfig to apply
        """
        from threadlight.context.composer import ContextComposer

        # Update identity settings
        self.tl.config.identity.system_prompt = model_config.system_prompt
        self.tl.config.style.default_profile = model_config.style_profile

        # Update memory settings
        self.tl.enable_memory = model_config.memory_enabled
        self.tl.config.memory.decay.enabled = model_config.decay_enabled

        # Update composer with new system prompt
        self.tl.composer = ContextComposer(
            identity_name=self.tl.config.identity.name,
            base_system_prompt=model_config.system_prompt,
        )

        # Load style profile if specified
        if model_config.style_profile:
            self.tl._load_style_profile(model_config.style_profile)
        else:
            self.tl.style_profile = None

    def get_current(self) -> 'ModelConfig':
        """
        Get config for currently active model.

        Returns:
            ModelConfig for the current model
        """
        return self.tl.config.get_model_config(self.tl.config.current_model)

    def update_current(self, **kwargs: Any) -> 'ModelConfig':
        """
        Update config for current model.

        Args:
            **kwargs: Fields to update (system_prompt, style_profile,
                      memory_enabled, decay_enabled, temperature, etc.)

        Returns:
            Updated ModelConfig
        """
        model_id = self.tl.config.current_model
        config = self.tl.config.update_model_config(model_id, **kwargs)

        # Apply the updated config
        self.apply(config)

        return config

    def list_available(self) -> list[dict[str, Any]]:
        """
        List all models with their configurations.

        Returns:
            List of model info dictionaries
        """
        models = []

        # Add configured models
        for model_id, model_config in self.tl.config.model_configs.items():
            if model_id == "default":
                continue  # Skip the default template
            models.append({
                "model_id": model_id,
                "is_current": model_id == self.tl.config.current_model,
                "config": model_config.to_dict(),
            })

        # Add current model if not in configs
        if self.tl.config.current_model not in self.tl.config.model_configs:
            current_config = self.get_current()
            models.insert(0, {
                "model_id": self.tl.config.current_model,
                "is_current": True,
                "config": current_config.to_dict(),
            })

        return models

    def create(
        self,
        model_id: str,
        system_prompt: Optional[str] = None,
        style_profile: Optional[str] = None,
        memory_enabled: bool = True,
        decay_enabled: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
    ) -> 'ModelConfig':
        """
        Create a new model configuration.

        Args:
            model_id: Model identifier
            system_prompt: Custom system prompt
            style_profile: Style profile to use
            memory_enabled: Whether to enable memory
            decay_enabled: Whether to enable memory decay
            temperature: Generation temperature
            max_tokens: Max tokens for generation
            top_p: Top-p sampling parameter

        Returns:
            The created ModelConfig
        """
        from threadlight.config import ModelConfig

        config = ModelConfig(
            model_id=model_id,
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            style_profile=style_profile,
            memory_enabled=memory_enabled,
            decay_enabled=decay_enabled,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        self.tl.config.set_model_config(model_id, config)
        return config

    def copy_settings(self, source_model: str, target_model: str) -> 'ModelConfig':
        """
        Copy settings from one model to another.

        Args:
            source_model: Model to copy from
            target_model: Model to copy to

        Returns:
            The new ModelConfig for target_model
        """
        return self.tl.config.copy_model_config(source_model, target_model)

    def delete(self, model_id: str) -> bool:
        """
        Delete a model configuration.

        Cannot delete the current model's config.

        Args:
            model_id: Model identifier to delete

        Returns:
            True if deleted, False otherwise
        """
        if model_id == self.tl.config.current_model:
            logger.warning("Cannot delete config for current model")
            return False
        return self.tl.config.delete_model_config(model_id)

    def enable_auto_save(
        self,
        path: Optional[str] = None,
        debounce_ms: int = 500,
    ) -> None:
        """
        Enable automatic config persistence.

        Config will be saved to disk after changes, with debouncing
        to avoid excessive writes.

        Args:
            path: Path to save config (default: ~/.config/threadlight/config.yaml)
            debounce_ms: Milliseconds to wait after last change before saving
        """
        save_path = Path(path) if path else None
        self.tl.config.enable_auto_save(save_path, debounce_ms)
        logger.info(f"Auto-save enabled: {save_path or '~/.config/threadlight/config.yaml'}")

    def disable_auto_save(self) -> None:
        """Disable automatic config persistence."""
        self.tl.config.disable_auto_save()
        logger.info("Auto-save disabled")
