"""
Profile management interface for Threadlight.

This module handles profile-related operations including:
- Switching between profiles
- Creating, updating, and deleting profiles
- Exporting and importing profiles
- Model selection based on profile settings
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.core import Threadlight

logger = logging.getLogger(__name__)


class ProfileInterface:
    """
    Manages profile operations for Threadlight.

    This interface handles:
    - Profile switching and application of profile settings
    - CRUD operations for profiles
    - Profile import/export
    - Model selection based on profile strategy
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the profile interface.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def switch(self, profile_id: str) -> 'Profile':
        """
        Switch to a different profile.

        This will:
        1. Load the profile from storage
        2. Update model configuration
        3. Apply profile's system prompt and style
        4. Update memory scope

        Args:
            profile_id: The profile ID to switch to

        Returns:
            The activated Profile

        Raises:
            ValueError: If profile not found
        """
        from threadlight.profiles import Profile
        profile = self.tl.profile_manager.switch_to(profile_id)
        self.apply(profile)
        return profile

    def apply(self, profile: 'Profile') -> None:
        """
        Apply a profile's settings to the current Threadlight instance.

        Args:
            profile: The profile to apply
        """
        from threadlight.profiles import AlloyedProfileEngine
        from threadlight.context.composer import ContextComposer

        self.tl.active_profile = profile

        # Initialize alloyed engine for model selection
        self.tl._alloyed_engine = AlloyedProfileEngine(profile, self.tl.storage)

        # Apply model configuration
        self.tl.provider.model = profile.primary_model
        self.tl.config.provider.model = profile.primary_model

        # Apply identity settings
        if profile.system_prompt:
            self.tl.config.identity.system_prompt = profile.system_prompt
            self.tl.composer = ContextComposer(
                identity_name=profile.name or self.tl.config.identity.name,
                base_system_prompt=profile.system_prompt,
            )
        elif profile.name:
            self.tl.composer = ContextComposer(
                identity_name=profile.name,
                base_system_prompt=self.tl.config.identity.system_prompt,
            )

        # Apply style profile if specified
        if profile.style_profile_id:
            self.tl._load_style_profile(profile.style_profile_id)

        # Update memory orchestrator's scope (profile takes precedence)
        self.tl.memory.current_profile = profile.memory_scope or profile.id
        self.tl.memory.current_model = profile.primary_model

        logger.info(f"Switched to profile: {profile.name} ({profile.id[:8]}...)")

    def clear(self) -> None:
        """Clear the active profile and revert to default settings."""
        from threadlight.context.composer import ContextComposer

        self.tl.active_profile = None
        self.tl._alloyed_engine = None

        # Restore default settings from config
        self.tl.provider.model = self.tl.config.provider.model
        self.tl.composer = ContextComposer(
            identity_name=self.tl.config.identity.name,
            base_system_prompt=self.tl.config.identity.system_prompt,
        )
        self.tl.memory.current_profile = None
        self.tl.memory.current_model = self.tl.config.provider.model

    def get_active(self) -> Optional['Profile']:
        """Get the currently active profile, if any."""
        return self.tl.active_profile

    def create(
        self,
        name: str,
        description: str = "",
        primary_model: Optional[str] = None,
        system_prompt: str = "",
        style_profile_id: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        temperature: float = 0.7,
        profile_id: Optional[str] = None,
        model_strategy: Optional['ModelStrategy'] = None,
        model_pool: Optional[list[str]] = None,
        model_weights: Optional[dict[str, float]] = None,
        routing_rules: Optional[list[dict]] = None,
        memory_scope: Optional[str] = None,
        access_shared_memories: bool = True,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        tags: Optional[list[str]] = None,
        philosophy: str = "",
        approach_to_rituals: str = "",
    ) -> 'Profile':
        """
        Create a new profile.

        Args:
            name: Display name for the profile
            description: One-line description
            primary_model: Model to use (defaults to current model)
            system_prompt: Base system prompt
            style_profile_id: Optional style profile to apply
            avatar: Optional avatar path/URL
            color: Optional hex color for UI
            temperature: Inference temperature
            profile_id: Optional custom ID (generated if not provided)
            model_strategy: Strategy for model selection (SINGLE, ALTERNATING, etc.)
            model_pool: List of models for multi-model strategies
            model_weights: Weight per model for WEIGHTED strategy
            routing_rules: Rules for ROUTED strategy
            memory_scope: Memory scope (defaults to profile ID)
            access_shared_memories: Whether to access shared memories
            max_tokens: Maximum tokens for responses
            top_p: Top-p sampling parameter
            tags: Optional tags for categorization
            philosophy: Freeform description of the profile's philosophy/approach
            approach_to_rituals: Freeform description of how rituals are handled

        Returns:
            The created Profile
        """
        from threadlight.profiles import ModelStrategy as MS

        return self.tl.profile_manager.create(
            name=name,
            description=description,
            primary_model=primary_model or self.tl.config.provider.model,
            system_prompt=system_prompt,
            style_profile_id=style_profile_id,
            avatar=avatar,
            color=color,
            temperature=temperature,
            profile_id=profile_id,
            model_strategy=model_strategy or MS.SINGLE,
            model_pool=model_pool,
            model_weights=model_weights,
            routing_rules=routing_rules,
            memory_scope=memory_scope,
            access_shared_memories=access_shared_memories,
            max_tokens=max_tokens,
            top_p=top_p,
            tags=tags,
            philosophy=philosophy,
            approach_to_rituals=approach_to_rituals,
        )

    def list(self) -> list['Profile']:
        """List all profiles."""
        return self.tl.profile_manager.list()

    def get(self, profile_id: str) -> Optional['Profile']:
        """Get a profile by ID."""
        return self.tl.profile_manager.get(profile_id)

    def update(self, profile_id: str, **kwargs) -> Optional['Profile']:
        """
        Update an existing profile.

        Args:
            profile_id: ID of the profile to update
            **kwargs: Fields to update (name, description, system_prompt, etc.)

        Returns:
            The updated Profile, or None if not found
        """
        from threadlight.profiles import ModelStrategy
        from threadlight.profiles.profile import RoutingRule

        profile = self.tl.profile_manager.get(profile_id)
        if not profile:
            return None

        # Update fields from kwargs
        for key, value in kwargs.items():
            if key == 'model_strategy' and value is not None:
                # Update alloyed_config strategy
                if profile.alloyed_config:
                    if isinstance(value, str):
                        profile.alloyed_config.strategy = ModelStrategy(value)
                    else:
                        profile.alloyed_config.strategy = value
            elif key == 'model_pool' and value is not None:
                if profile.alloyed_config:
                    profile.alloyed_config.model_pool = value
            elif key == 'model_weights' and value is not None:
                if profile.alloyed_config:
                    profile.alloyed_config.weights = value
            elif key == 'routing_rules' and value is not None:
                if profile.alloyed_config:
                    parsed_rules = []
                    for rule in value:
                        if isinstance(rule, dict):
                            parsed_rules.append(RoutingRule.from_dict(rule))
                        else:
                            parsed_rules.append(rule)
                    profile.alloyed_config.routing_rules = parsed_rules
            elif hasattr(profile, key):
                setattr(profile, key, value)

        self.tl.profile_manager.update(profile)

        # If this is the active profile, re-apply settings
        if self.tl.active_profile and self.tl.active_profile.id == profile.id:
            self.apply(profile)

        return profile

    def delete(self, profile_id: str) -> bool:
        """Delete a profile."""
        # Clear active profile if it's being deleted
        if self.tl.active_profile and self.tl.active_profile.id == profile_id:
            self.clear()

        return self.tl.profile_manager.delete(profile_id)

    def export(
        self,
        profile_id: str,
        include_memories: bool = False,
        include_conversations: bool = False,
    ) -> dict:
        """
        Export a profile to a dictionary.

        Args:
            profile_id: The profile ID to export
            include_memories: Whether to include profile memories
            include_conversations: Whether to include conversations

        Returns:
            Dictionary containing profile data and optional extras
        """
        return self.tl.profile_manager.export_profile(
            profile_id,
            include_memories=include_memories,
            include_conversations=include_conversations,
        )

    def import_profile(self, export_data: dict) -> 'Profile':
        """
        Import a profile from exported data.

        Args:
            export_data: Dictionary containing exported profile data

        Returns:
            The imported Profile
        """
        return self.tl.profile_manager.import_profile(export_data)

    def get_model_for_message(self, message: str) -> str:
        """
        Get the model to use for a message, considering profile settings.

        If an alloyed profile is active, uses the AlloyedProfileEngine
        to select the appropriate model based on the profile's strategy.

        Args:
            message: The user's message

        Returns:
            Model identifier to use
        """
        if self.tl._alloyed_engine:
            return self.tl._alloyed_engine.select_model(message)
        return self.tl.config.provider.model
