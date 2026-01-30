"""
ProfileManager for Threadlight.

Manages profile CRUD operations, caching, and switching between profiles.
"""

from typing import Optional
from datetime import datetime
import uuid

from threadlight.profiles.profile import Profile, ModelStrategy, AlloyedConfig
from threadlight.storage.base import StorageBackend


class ProfileManager:
    """
    Manages profiles with caching and CRUD operations.

    The ProfileManager provides a high-level interface for working with profiles,
    including creation, retrieval, updates, deletion, and switching between profiles.
    """

    def __init__(self, storage: StorageBackend):
        """
        Initialize ProfileManager.

        Args:
            storage: Storage backend for persisting profiles
        """
        self.storage = storage
        self._cache: dict[str, Profile] = {}
        self._active_profile_id: Optional[str] = None

    def create(
        self,
        name: str,
        description: str = "",
        primary_model: str = "nous-research/hermes-3-llama-3.1-405b",
        system_prompt: str = "",
        style_profile_id: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        temperature: float = 0.7,
        profile_id: Optional[str] = None,
        model_strategy: ModelStrategy = ModelStrategy.SINGLE,
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
    ) -> Profile:
        """
        Create a new profile.

        Args:
            name: Display name for the profile
            description: One-line description
            primary_model: Model to use for this profile
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
        from threadlight.profiles.profile import RoutingRule

        if profile_id is None:
            profile_id = str(uuid.uuid4())

        # Build alloyed config
        if model_pool is None:
            model_pool = [primary_model]

        parsed_rules = []
        if routing_rules:
            for rule in routing_rules:
                if isinstance(rule, dict):
                    parsed_rules.append(RoutingRule.from_dict(rule))
                else:
                    parsed_rules.append(rule)

        alloyed_config = AlloyedConfig(
            strategy=model_strategy,
            model_pool=model_pool,
            weights=model_weights,
            routing_rules=parsed_rules,
        )

        profile = Profile(
            id=profile_id,
            name=name,
            description=description,
            primary_model=primary_model,
            system_prompt=system_prompt,
            style_profile_id=style_profile_id,
            avatar=avatar,
            color=color,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            alloyed_config=alloyed_config,
            memory_scope=memory_scope or profile_id,
            access_shared_memories=access_shared_memories,
            philosophy=philosophy,
            approach_to_rituals=approach_to_rituals,
        )

        # Save to storage
        self.storage.save_profile(profile)

        # Cache it
        self._cache[profile.id] = profile

        return profile

    def get(self, profile_id: str) -> Optional[Profile]:
        """
        Get a profile by ID.

        Args:
            profile_id: The profile ID

        Returns:
            The Profile, or None if not found
        """
        # Check cache first
        if profile_id in self._cache:
            return self._cache[profile_id]

        # Load from storage
        profile = self.storage.get_profile(profile_id)
        if profile:
            self._cache[profile_id] = profile

        return profile

    def update(self, profile: Profile) -> None:
        """
        Update an existing profile.

        Args:
            profile: The profile to update
        """
        profile.updated_at = datetime.now()

        # Update in storage
        self.storage.update_profile(profile)

        # Update cache
        self._cache[profile.id] = profile

    def delete(self, profile_id: str) -> bool:
        """
        Delete a profile.

        Args:
            profile_id: The profile ID to delete

        Returns:
            True if deleted, False if not found
        """
        # Remove from cache
        self._cache.pop(profile_id, None)

        # If this was the active profile, clear it
        if self._active_profile_id == profile_id:
            self._active_profile_id = None

        # Delete from storage
        return self.storage.delete_profile(profile_id)

    def list(self) -> list[Profile]:
        """
        List all profiles.

        Returns:
            List of all profiles
        """
        profiles = self.storage.list_profiles()

        # Update cache
        for profile in profiles:
            self._cache[profile.id] = profile

        return profiles

    def switch_to(self, profile_id: str) -> Profile:
        """
        Switch to a different profile.

        Args:
            profile_id: The profile ID to switch to

        Returns:
            The activated profile

        Raises:
            ValueError: If profile not found
        """
        profile = self.get(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Update last_used_at
        profile.last_used_at = datetime.now()
        self.update(profile)

        # Set as active
        self._active_profile_id = profile_id

        return profile

    def get_active(self) -> Optional[Profile]:
        """
        Get the currently active profile.

        Returns:
            The active Profile, or None if no profile is active
        """
        if self._active_profile_id is None:
            return None

        return self.get(self._active_profile_id)

    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()

    def export_profile(
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

        Raises:
            ValueError: If profile not found
        """
        profile = self.get(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        export_data = {
            "version": "1.0",
            "profile": profile.to_dict(),
        }

        if include_memories:
            # Get memories scoped to this profile
            from threadlight.storage.base import CapsuleFilter

            filter_ = CapsuleFilter(profile_scope=profile_id)
            capsules = self.storage.list_capsules(filter_)
            export_data["memories"] = [c.to_dict() for c in capsules]

        if include_conversations:
            # Get conversations for this profile
            conversations = self.storage.list_conversations()
            # Filter conversations that have messages from this profile
            # (This would need profile_id on messages, which we'll add in Phase 2)
            export_data["conversations"] = [c.to_dict() for c in conversations]

        return export_data

    def import_profile(self, export_data: dict) -> Profile:
        """
        Import a profile from exported data.

        Args:
            export_data: Dictionary containing exported profile data

        Returns:
            The imported Profile

        Raises:
            ValueError: If export data is invalid
        """
        if "profile" not in export_data:
            raise ValueError("Invalid export data: missing 'profile' field")

        # Create profile from data
        profile_data = export_data["profile"]
        profile = Profile.from_dict(profile_data)

        # Generate new ID to avoid conflicts
        old_id = profile.id
        profile.id = str(uuid.uuid4())
        profile.created_at = datetime.now()
        profile.updated_at = datetime.now()

        # Save profile
        self.storage.save_profile(profile)
        self._cache[profile.id] = profile

        # Import memories if included
        if "memories" in export_data:
            for memory_data in export_data["memories"]:
                # Update profile_scope to new profile ID
                if memory_data.get("profile_scope") == old_id:
                    memory_data["profile_scope"] = profile.id

                # Import the memory
                # (Would use MemoryOrchestrator.create() in practice)
                pass

        return profile
