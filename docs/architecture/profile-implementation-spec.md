# Threadlight Profile System - Implementation Specification

## Overview

This document provides detailed implementation specifications for the profile-based architecture. It covers file-by-file changes, database migrations, and implementation order.

---

## 1. File Structure

### New Files to Create

```
src/threadlight/
├── profiles/
│   ├── __init__.py              # Exports
│   ├── profile.py               # Profile dataclass
│   ├── manager.py               # ProfileManager class
│   ├── alloyed.py               # AlloyedProfileEngine
│   ├── strategies.py            # Model selection strategies
│   └── templates.py             # Built-in profile templates
├── group_chat/
│   ├── __init__.py
│   ├── group.py                 # GroupChat class
│   ├── turn_order.py            # Turn order strategies
│   └── context.py               # Group context builders
```

### Files to Modify

```
src/threadlight/
├── core.py                      # Add profile support
├── config.py                    # Add profile config section
├── storage/
│   ├── base.py                  # Add profile storage interface
│   └── sqlite.py                # Implement profile storage
├── capsules/
│   └── base.py                  # Add profile_scope field
├── memory/
│   └── orchestrator.py          # Profile-scoped memory operations
├── context/
│   └── composer.py              # Profile context composition
```

---

## 2. Core Data Structures

### 2.1 Profile Dataclass (`profiles/profile.py`)

```python
"""
Profile data model for Threadlight.

A Profile represents a persistent persona with its own identity,
memories, and model configuration.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ModelStrategy(str, Enum):
    """How a profile selects which model to use."""

    SINGLE = "single"
    ALTERNATING = "alternating"
    RATIO = "ratio"
    WEIGHTED = "weighted"
    DYNAMIC = "dynamic"
    ROUND_ROBIN = "round_robin"


@dataclass
class RoutingRule:
    """Rule for dynamic model selection."""

    condition_type: str  # "keyword", "regex", "intent", "length"
    condition_value: str
    model: str
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_type": self.condition_type,
            "condition_value": self.condition_value,
            "model": self.model,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingRule":
        return cls(
            condition_type=data["condition_type"],
            condition_value=data["condition_value"],
            model=data["model"],
            priority=data.get("priority", 0),
        )


@dataclass
class AlloyedConfig:
    """Configuration for alloyed (multi-model) profiles."""

    strategy: ModelStrategy = ModelStrategy.SINGLE

    # For RATIO strategy: ordered list of models
    ratio_pattern: list[str] = field(default_factory=list)

    # For WEIGHTED strategy: model -> weight
    weights: dict[str, float] = field(default_factory=dict)

    # For DYNAMIC strategy: routing rules
    routing_rules: list[RoutingRule] = field(default_factory=list)

    # State tracking
    current_index: int = 0
    turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "ratio_pattern": self.ratio_pattern,
            "weights": self.weights,
            "routing_rules": [r.to_dict() for r in self.routing_rules],
            "current_index": self.current_index,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlloyedConfig":
        return cls(
            strategy=ModelStrategy(data.get("strategy", "single")),
            ratio_pattern=data.get("ratio_pattern", []),
            weights=data.get("weights", {}),
            routing_rules=[
                RoutingRule.from_dict(r)
                for r in data.get("routing_rules", [])
            ],
            current_index=data.get("current_index", 0),
            turn_count=data.get("turn_count", 0),
        )


@dataclass
class Profile:
    """
    A Profile represents a persistent persona in Threadlight.

    Profiles are first-class citizens that own their memories,
    define their personality, and can use any supported model.
    """

    # Core Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    avatar: Optional[str] = None
    color: Optional[str] = None  # Hex color like "#6366f1"

    # Model Configuration
    model_strategy: ModelStrategy = ModelStrategy.SINGLE
    primary_model: str = "Hermes-4.3-36B"
    model_pool: list[str] = field(default_factory=list)
    model_pattern: Optional[dict[str, Any]] = None  # AlloyedConfig as dict

    # Inference Settings
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    # Personality
    system_prompt: str = ""
    style_profile_id: Optional[str] = None

    # Memory Configuration
    memory_scope: str = ""  # Defaults to profile ID
    access_shared_memories: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    is_archived: bool = False

    # Runtime state (not persisted directly)
    _alloyed_config: Optional[AlloyedConfig] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # Set memory_scope to ID if not specified
        if not self.memory_scope:
            self.memory_scope = self.id

        # Parse alloyed config if model_pattern exists
        if self.model_pattern and not self._alloyed_config:
            self._alloyed_config = AlloyedConfig.from_dict(self.model_pattern)

    @property
    def alloyed_config(self) -> AlloyedConfig:
        """Get the alloyed configuration, creating default if needed."""
        if self._alloyed_config is None:
            self._alloyed_config = AlloyedConfig(strategy=self.model_strategy)
        return self._alloyed_config

    def get_display_model(self) -> str:
        """Get the display name for this profile's model configuration."""
        if self.model_strategy == ModelStrategy.SINGLE:
            return self.primary_model
        elif self.model_pool:
            return f"{self.primary_model} + {len(self.model_pool) - 1} others"
        return self.primary_model

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "avatar": self.avatar,
            "color": self.color,
            "model_strategy": self.model_strategy.value,
            "primary_model": self.primary_model,
            "model_pool": self.model_pool,
            "model_pattern": self.alloyed_config.to_dict() if self._alloyed_config else None,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "system_prompt": self.system_prompt,
            "style_profile_id": self.style_profile_id,
            "memory_scope": self.memory_scope,
            "access_shared_memories": self.access_shared_memories,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "message_count": self.message_count,
            "is_archived": self.is_archived,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""

        def parse_datetime(val):
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return datetime.utcnow()

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            avatar=data.get("avatar"),
            color=data.get("color"),
            model_strategy=ModelStrategy(data.get("model_strategy", "single")),
            primary_model=data.get("primary_model", "Hermes-4.3-36B"),
            model_pool=data.get("model_pool", []),
            model_pattern=data.get("model_pattern"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p", 1.0),
            system_prompt=data.get("system_prompt", ""),
            style_profile_id=data.get("style_profile_id"),
            memory_scope=data.get("memory_scope", data.get("id", "")),
            access_shared_memories=data.get("access_shared_memories", True),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            last_used=parse_datetime(data.get("last_used")),
            message_count=data.get("message_count", 0),
            is_archived=data.get("is_archived", False),
        )

    def __repr__(self) -> str:
        return f"<Profile name={self.name!r} model={self.primary_model!r}>"
```

### 2.2 Alloyed Profile Engine (`profiles/alloyed.py`)

```python
"""
Alloyed profile engine for multi-model selection.

Handles model selection strategies for profiles that use multiple models.
"""

from __future__ import annotations

import random
import re
from typing import Optional

from threadlight.profiles.profile import (
    Profile,
    ModelStrategy,
    AlloyedConfig,
    RoutingRule,
)


class AlloyedProfileEngine:
    """
    Engine for selecting models in alloyed (multi-model) profiles.

    Supports various strategies:
    - SINGLE: Always use primary_model
    - ALTERNATING: Cycle through model_pool
    - RATIO: Follow a pattern like [H, H, C, H, H, C]
    - WEIGHTED: Random selection with weights
    - DYNAMIC: Rule-based selection
    - ROUND_ROBIN: Cycle through all models equally
    """

    def __init__(self, profile: Profile, on_state_change: Optional[callable] = None):
        """
        Initialize the engine.

        Args:
            profile: The profile to manage
            on_state_change: Callback when state changes (for persistence)
        """
        self.profile = profile
        self.on_state_change = on_state_change

    @property
    def config(self) -> AlloyedConfig:
        """Get the profile's alloyed configuration."""
        return self.profile.alloyed_config

    def get_next_model(self, message: str = "") -> str:
        """
        Determine which model to use for the next turn.

        Args:
            message: The user's message (used for DYNAMIC strategy)

        Returns:
            Model identifier to use
        """
        strategy = self.profile.model_strategy

        if strategy == ModelStrategy.SINGLE:
            return self.profile.primary_model

        elif strategy == ModelStrategy.ALTERNATING:
            return self._alternating_selection()

        elif strategy == ModelStrategy.RATIO:
            return self._ratio_selection()

        elif strategy == ModelStrategy.WEIGHTED:
            return self._weighted_selection()

        elif strategy == ModelStrategy.DYNAMIC:
            return self._dynamic_selection(message)

        elif strategy == ModelStrategy.ROUND_ROBIN:
            return self._round_robin_selection()

        return self.profile.primary_model

    def _alternating_selection(self) -> str:
        """Alternate between models each turn."""
        pool = self._get_model_pool()
        if not pool:
            return self.profile.primary_model

        idx = self.config.current_index % len(pool)
        model = pool[idx]

        # Advance state
        self.config.current_index += 1
        self._notify_state_change()

        return model

    def _ratio_selection(self) -> str:
        """Select based on ratio pattern."""
        pattern = self.config.ratio_pattern
        if not pattern:
            return self.profile.primary_model

        idx = self.config.turn_count % len(pattern)
        model = pattern[idx]

        # Advance state
        self.config.turn_count += 1
        self._notify_state_change()

        return model

    def _weighted_selection(self) -> str:
        """Random selection with weights."""
        weights = self.config.weights
        if not weights:
            return self.profile.primary_model

        models = list(weights.keys())
        weight_values = [weights[m] for m in models]

        return random.choices(models, weights=weight_values, k=1)[0]

    def _dynamic_selection(self, message: str) -> str:
        """Choose model based on message content using routing rules."""
        rules = self.config.routing_rules
        if not rules:
            return self.profile.primary_model

        # Sort by priority (higher first)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if self._matches_rule(message, rule):
                return rule.model

        return self.profile.primary_model

    def _round_robin_selection(self) -> str:
        """Cycle through all models in pool."""
        pool = self._get_model_pool()
        if not pool:
            return self.profile.primary_model

        idx = self.config.current_index % len(pool)
        model = pool[idx]

        # Advance state
        self.config.current_index += 1
        self._notify_state_change()

        return model

    def _get_model_pool(self) -> list[str]:
        """Get the pool of available models."""
        if self.profile.model_pool:
            return self.profile.model_pool
        return [self.profile.primary_model]

    def _matches_rule(self, message: str, rule: RoutingRule) -> bool:
        """Check if a message matches a routing rule."""
        condition_type = rule.condition_type.lower()
        value = rule.condition_value

        if condition_type == "keyword":
            return value.lower() in message.lower()

        elif condition_type == "regex":
            try:
                return bool(re.search(value, message, re.IGNORECASE))
            except re.error:
                return False

        elif condition_type == "length":
            length = len(message)
            if value == "short":
                return length < 50
            elif value == "medium":
                return 50 <= length <= 200
            elif value == "long":
                return length > 200

        elif condition_type == "starts_with":
            return message.lower().startswith(value.lower())

        elif condition_type == "ends_with":
            return message.lower().endswith(value.lower())

        return False

    def _notify_state_change(self) -> None:
        """Notify that state has changed (for persistence)."""
        # Update the model_pattern in profile
        self.profile.model_pattern = self.config.to_dict()

        if self.on_state_change:
            self.on_state_change(self.profile)

    def reset_state(self) -> None:
        """Reset alloyed state to initial values."""
        self.config.current_index = 0
        self.config.turn_count = 0
        self._notify_state_change()

    def get_state_info(self) -> dict:
        """Get current state information for debugging/UI."""
        return {
            "strategy": self.profile.model_strategy.value,
            "current_index": self.config.current_index,
            "turn_count": self.config.turn_count,
            "next_model": self.get_next_model(),
            "model_pool": self._get_model_pool(),
        }
```

### 2.3 Profile Manager (`profiles/manager.py`)

```python
"""
Profile manager for Threadlight.

Handles profile CRUD, switching, and state management.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Any, Optional

from threadlight.profiles.profile import Profile, ModelStrategy
from threadlight.profiles.templates import PROFILE_TEMPLATES
from threadlight.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Central manager for profile operations.

    Handles:
    - Profile CRUD operations
    - Profile switching
    - Profile templates
    - Export/Import
    """

    def __init__(self, storage: StorageBackend):
        """
        Initialize the profile manager.

        Args:
            storage: Storage backend for persistence
        """
        self.storage = storage
        self._active_profile: Optional[Profile] = None
        self._cache: dict[str, Profile] = {}

    # === CRUD Operations ===

    def create_profile(
        self,
        name: str,
        description: str = "",
        primary_model: str = "Hermes-4.3-36B",
        system_prompt: Optional[str] = None,
        style_profile_id: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        model_strategy: ModelStrategy = ModelStrategy.SINGLE,
        model_pool: Optional[list[str]] = None,
        model_pattern: Optional[dict] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        access_shared_memories: bool = True,
    ) -> Profile:
        """
        Create a new profile.

        Args:
            name: Display name for the profile
            description: Short description
            primary_model: Default model to use
            system_prompt: Base personality prompt
            style_profile_id: Style profile to apply
            avatar: Path or URL to avatar
            color: Hex color for UI
            model_strategy: How to select models
            model_pool: Available models for alloyed profiles
            model_pattern: Configuration for alloyed profiles
            temperature: Default temperature
            max_tokens: Default max tokens
            access_shared_memories: Whether to see shared memories

        Returns:
            The created Profile
        """
        profile_id = str(uuid.uuid4())

        # Default system prompt includes the name
        if system_prompt is None:
            system_prompt = f"You are {name}."

        profile = Profile(
            id=profile_id,
            name=name,
            description=description,
            avatar=avatar,
            color=color,
            model_strategy=model_strategy,
            primary_model=primary_model,
            model_pool=model_pool or [],
            model_pattern=model_pattern,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            style_profile_id=style_profile_id,
            memory_scope=profile_id,
            access_shared_memories=access_shared_memories,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
        )

        self.storage.save_profile(profile)
        self._cache[profile_id] = profile

        logger.info(f"Created profile: {name} ({profile_id})")
        return profile

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        # Check cache first
        if profile_id in self._cache:
            return self._cache[profile_id]

        # Load from storage
        profile = self.storage.get_profile(profile_id)
        if profile:
            self._cache[profile_id] = profile

        return profile

    def get_profile_by_name(self, name: str) -> Optional[Profile]:
        """Get a profile by name (case-insensitive)."""
        profiles = self.list_profiles()
        name_lower = name.lower()

        for profile in profiles:
            if profile.name.lower() == name_lower:
                return profile

        return None

    def update_profile(self, profile: Profile) -> bool:
        """Update an existing profile."""
        profile.updated_at = datetime.utcnow()

        success = self.storage.update_profile(profile)
        if success:
            self._cache[profile.id] = profile

        return success

    def delete_profile(
        self,
        profile_id: str,
        delete_memories: bool = False,
    ) -> bool:
        """
        Delete a profile.

        Args:
            profile_id: Profile to delete
            delete_memories: If True, also delete profile's memories

        Returns:
            True if deleted successfully
        """
        # Check if this is the active profile
        if self._active_profile and self._active_profile.id == profile_id:
            self._active_profile = None

        # Delete memories if requested
        if delete_memories:
            self.storage.delete_capsules_by_scope(profile_id)
            self.storage.delete_conversations_by_profile(profile_id)

        # Delete the profile
        success = self.storage.delete_profile(profile_id)

        if success:
            self._cache.pop(profile_id, None)
            logger.info(f"Deleted profile: {profile_id}")

        return success

    def list_profiles(
        self,
        limit: int = 100,
        include_archived: bool = False,
        order_by: str = "last_used",
    ) -> list[Profile]:
        """
        List all profiles.

        Args:
            limit: Maximum profiles to return
            include_archived: Include archived profiles
            order_by: Sort field (last_used, name, created_at)

        Returns:
            List of profiles
        """
        return self.storage.list_profiles(
            limit=limit,
            include_archived=include_archived,
            order_by=order_by,
        )

    def archive_profile(self, profile_id: str) -> bool:
        """Archive a profile (soft delete)."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False

        profile.is_archived = True
        return self.update_profile(profile)

    def unarchive_profile(self, profile_id: str) -> bool:
        """Unarchive a profile."""
        profile = self.get_profile(profile_id)
        if not profile:
            return False

        profile.is_archived = False
        return self.update_profile(profile)

    # === Profile Switching ===

    def switch_to_profile(self, profile_id: str) -> Optional[Profile]:
        """
        Switch the active profile.

        Args:
            profile_id: Profile to switch to

        Returns:
            The activated profile, or None if not found
        """
        profile = self.get_profile(profile_id)
        if not profile:
            logger.warning(f"Profile not found: {profile_id}")
            return None

        self._active_profile = profile

        # Update last_used
        profile.last_used = datetime.utcnow()
        self.update_profile(profile)

        logger.info(f"Switched to profile: {profile.name}")
        return profile

    def switch_to_profile_by_name(self, name: str) -> Optional[Profile]:
        """Switch to a profile by name."""
        profile = self.get_profile_by_name(name)
        if profile:
            return self.switch_to_profile(profile.id)
        return None

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile."""
        return self._active_profile

    def clear_active_profile(self) -> None:
        """Clear the active profile."""
        self._active_profile = None

    # === Templates ===

    def create_from_template(
        self,
        template_name: str,
        name: str,
        **overrides: Any,
    ) -> Profile:
        """
        Create a profile from a template.

        Args:
            template_name: Name of the template
            name: Name for the new profile
            **overrides: Fields to override from template

        Returns:
            The created profile

        Raises:
            ValueError: If template not found
        """
        if template_name not in PROFILE_TEMPLATES:
            available = ", ".join(PROFILE_TEMPLATES.keys())
            raise ValueError(
                f"Unknown template: {template_name}. "
                f"Available: {available}"
            )

        template = PROFILE_TEMPLATES[template_name].copy()
        template.update(overrides)
        template["name"] = name

        return self.create_profile(**template)

    def get_templates(self) -> dict[str, dict[str, Any]]:
        """Get available profile templates."""
        return PROFILE_TEMPLATES.copy()

    def list_template_names(self) -> list[str]:
        """List available template names."""
        return list(PROFILE_TEMPLATES.keys())

    # === Export/Import ===

    def export_profile(
        self,
        profile_id: str,
        include_memories: bool = True,
        include_conversations: bool = False,
    ) -> dict[str, Any]:
        """
        Export a profile to a portable format.

        Args:
            profile_id: Profile to export
            include_memories: Include profile's memories
            include_conversations: Include profile's conversations

        Returns:
            Export data dictionary

        Raises:
            ValueError: If profile not found
        """
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        export_data = {
            "version": "1.0",
            "export_type": "profile",
            "exported_at": datetime.utcnow().isoformat(),
            "profile": profile.to_dict(),
        }

        if include_memories:
            from threadlight.storage.base import CapsuleFilter

            memories = self.storage.list_capsules(
                CapsuleFilter(profile_scope=profile.memory_scope)
            )
            export_data["memories"] = [m.to_dict() for m in memories]
            export_data["memory_count"] = len(memories)

        if include_conversations:
            conversations = self.storage.list_conversations_for_profile(profile_id)
            export_data["conversations"] = []

            for conv in conversations:
                conv_data = {
                    "conversation": conv.to_dict() if hasattr(conv, 'to_dict') else conv,
                    "messages": [],
                }
                messages = self.storage.get_messages(conv.id)
                conv_data["messages"] = [
                    m.to_dict() if hasattr(m, 'to_dict') else m
                    for m in messages
                ]
                export_data["conversations"].append(conv_data)

        return export_data

    def import_profile(
        self,
        export_data: dict[str, Any],
        new_name: Optional[str] = None,
    ) -> Profile:
        """
        Import a profile from exported data.

        Args:
            export_data: Data from export_profile()
            new_name: Override the profile name

        Returns:
            The imported profile
        """
        # Validate version
        version = export_data.get("version", "1.0")
        if version != "1.0":
            logger.warning(f"Unknown export version: {version}")

        profile_data = export_data["profile"]

        # Generate new IDs to avoid conflicts
        new_profile_id = str(uuid.uuid4())
        new_memory_scope = new_profile_id

        profile_data["id"] = new_profile_id
        profile_data["memory_scope"] = new_memory_scope
        profile_data["created_at"] = datetime.utcnow().isoformat()
        profile_data["updated_at"] = datetime.utcnow().isoformat()
        profile_data["message_count"] = 0

        if new_name:
            profile_data["name"] = new_name

        profile = Profile.from_dict(profile_data)
        self.storage.save_profile(profile)
        self._cache[profile.id] = profile

        # Import memories
        if "memories" in export_data:
            from threadlight.capsules.factory import create_capsule

            for memory_data in export_data["memories"]:
                memory_data["id"] = str(uuid.uuid4())
                memory_data["profile_scope"] = new_memory_scope
                capsule = create_capsule(memory_data)
                self.storage.save_capsule(capsule)

            logger.info(
                f"Imported {len(export_data['memories'])} memories "
                f"for profile {profile.name}"
            )

        # Import conversations
        if "conversations" in export_data:
            for conv_data in export_data["conversations"]:
                # Create new conversation ID
                conv_info = conv_data["conversation"]
                new_conv_id = str(uuid.uuid4())

                # Update conversation
                from threadlight.storage.base import Conversation

                conv = Conversation(
                    id=new_conv_id,
                    name=conv_info.get("name", ""),
                    profile_id=new_profile_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self.storage.save_conversation(conv)

                # Import messages
                for msg_data in conv_data.get("messages", []):
                    from threadlight.storage.base import Message

                    msg = Message(
                        id=str(uuid.uuid4()),
                        conversation_id=new_conv_id,
                        role=msg_data["role"],
                        content=msg_data["content"],
                        profile_id=new_profile_id if msg_data["role"] == "assistant" else None,
                        timestamp=datetime.utcnow(),
                    )
                    self.storage.save_message(msg)

        logger.info(f"Imported profile: {profile.name} ({profile.id})")
        return profile

    # === Utility ===

    def clear_cache(self) -> None:
        """Clear the profile cache."""
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get profile statistics."""
        profiles = self.list_profiles(include_archived=True)

        return {
            "total_profiles": len(profiles),
            "active_profiles": sum(1 for p in profiles if not p.is_archived),
            "archived_profiles": sum(1 for p in profiles if p.is_archived),
            "current_profile": self._active_profile.name if self._active_profile else None,
            "profiles_by_strategy": self._count_by_strategy(profiles),
        }

    def _count_by_strategy(self, profiles: list[Profile]) -> dict[str, int]:
        """Count profiles by model strategy."""
        counts: dict[str, int] = {}
        for p in profiles:
            strategy = p.model_strategy.value
            counts[strategy] = counts.get(strategy, 0) + 1
        return counts
```

---

## 3. Database Migrations

### 3.1 Add Profiles Table

```python
# In storage/sqlite.py - add to initialize() method

def _create_profiles_table(self) -> None:
    """Create the profiles table."""
    self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            avatar TEXT,
            color TEXT,

            -- Model configuration
            model_strategy TEXT DEFAULT 'single',
            primary_model TEXT NOT NULL,
            model_pool TEXT,           -- JSON array
            model_pattern TEXT,        -- JSON config

            -- Inference settings
            temperature REAL DEFAULT 0.7,
            max_tokens INTEGER,
            top_p REAL DEFAULT 1.0,

            -- Personality
            system_prompt TEXT,
            style_profile_id TEXT,

            -- Memory
            memory_scope TEXT NOT NULL,
            access_shared_memories INTEGER DEFAULT 1,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used TEXT,
            message_count INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);
        CREATE INDEX IF NOT EXISTS idx_profiles_last_used ON profiles(last_used);
        CREATE INDEX IF NOT EXISTS idx_profiles_archived ON profiles(is_archived);
    """)
```

### 3.2 Add profile_scope to Capsules

```python
def _migrate_add_profile_scope(self) -> None:
    """Add profile_scope column to capsules table."""
    cursor = self.conn.execute("PRAGMA table_info(capsules)")
    columns = [row[1] for row in cursor.fetchall()]

    if "profile_scope" not in columns:
        self.conn.execute("ALTER TABLE capsules ADD COLUMN profile_scope TEXT")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_capsules_profile_scope "
            "ON capsules(profile_scope)"
        )

        # Migrate existing model_scope data to profile_scope
        self.conn.execute(
            "UPDATE capsules SET profile_scope = model_scope "
            "WHERE model_scope IS NOT NULL"
        )

        self.conn.commit()
```

### 3.3 Add Profile Attribution to Messages

```python
def _migrate_messages_profile(self) -> None:
    """Add profile attribution to messages."""
    cursor = self.conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]

    if "profile_id" not in columns:
        self.conn.execute("ALTER TABLE messages ADD COLUMN profile_id TEXT")
        self.conn.execute("ALTER TABLE messages ADD COLUMN model_used TEXT")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_profile "
            "ON messages(profile_id)"
        )
        self.conn.commit()
```

---

## 4. Storage Interface Extensions

### 4.1 StorageBackend Profile Methods

```python
# Add to storage/base.py - StorageBackend class

# Profile operations
def save_profile(self, profile: Profile) -> str:
    """Save a profile to storage."""
    raise NotImplementedError

def get_profile(self, profile_id: str) -> Optional[Profile]:
    """Get a profile by ID."""
    raise NotImplementedError

def update_profile(self, profile: Profile) -> bool:
    """Update an existing profile."""
    raise NotImplementedError

def delete_profile(self, profile_id: str) -> bool:
    """Delete a profile."""
    raise NotImplementedError

def list_profiles(
    self,
    limit: int = 100,
    include_archived: bool = False,
    order_by: str = "last_used",
) -> list[Profile]:
    """List profiles."""
    raise NotImplementedError

def delete_capsules_by_scope(self, profile_scope: str) -> int:
    """Delete all capsules in a profile scope."""
    raise NotImplementedError

def delete_conversations_by_profile(self, profile_id: str) -> int:
    """Delete all conversations for a profile."""
    raise NotImplementedError

def list_conversations_for_profile(
    self,
    profile_id: str,
    limit: int = 100,
) -> list[Conversation]:
    """List conversations for a profile."""
    raise NotImplementedError
```

---

## 5. Implementation Order

### Phase 1: Core Profile Support (Days 1-3)

1. Create `profiles/profile.py` with Profile dataclass
2. Create `profiles/manager.py` with basic CRUD
3. Add profiles table to SQLite storage
4. Implement storage methods for profiles
5. Write unit tests for Profile and ProfileManager

### Phase 2: Memory Integration (Days 4-5)

1. Add `profile_scope` to capsules
2. Update `CapsuleFilter` to support `profile_scope`
3. Migrate `model_scope` to `profile_scope`
4. Update `MemoryOrchestrator` for profile-scoped operations
5. Write integration tests

### Phase 3: Alloyed Profiles (Days 6-7)

1. Create `profiles/alloyed.py` with AlloyedProfileEngine
2. Implement all model selection strategies
3. Add state persistence
4. Write unit tests for each strategy

### Phase 4: Threadlight Integration (Days 8-9)

1. Update `Threadlight.__init__` for profile loading
2. Add `switch_profile()` method
3. Integrate alloyed engine with chat flow
4. Update context composer for profiles
5. Write integration tests

### Phase 5: Polish (Days 10-11)

1. Create `profiles/templates.py` with built-in templates
2. Implement export/import functionality
3. Add profile statistics
4. Documentation and examples

---

## 6. Testing Strategy

### Unit Tests

```python
# tests/test_profiles.py

class TestProfile:
    def test_create_profile(self):
        """Test profile creation with defaults."""

    def test_profile_serialization(self):
        """Test to_dict and from_dict."""

    def test_memory_scope_defaults_to_id(self):
        """Test that memory_scope defaults to profile ID."""


class TestAlloyedEngine:
    def test_single_strategy(self):
        """Test SINGLE strategy always returns primary_model."""

    def test_alternating_strategy(self):
        """Test ALTERNATING cycles through pool."""

    def test_ratio_strategy(self):
        """Test RATIO follows pattern correctly."""

    def test_weighted_strategy(self):
        """Test WEIGHTED respects weights over many iterations."""

    def test_dynamic_keyword_routing(self):
        """Test DYNAMIC routes based on keywords."""

    def test_state_persistence(self):
        """Test that state changes trigger callbacks."""


class TestProfileManager:
    def test_crud_operations(self):
        """Test create, read, update, delete."""

    def test_switch_profile(self):
        """Test profile switching."""

    def test_template_creation(self):
        """Test creating profiles from templates."""

    def test_export_import(self):
        """Test export and import preserves data."""
```

### Integration Tests

```python
# tests/test_profile_integration.py

class TestProfileMemoryIsolation:
    def test_profiles_have_separate_memories(self):
        """Test that profiles don't see each other's memories."""

    def test_shared_memories_visible_to_all(self):
        """Test that shared memories are visible across profiles."""

    def test_access_shared_memories_flag(self):
        """Test that access_shared_memories controls visibility."""


class TestProfileChat:
    def test_chat_uses_profile_system_prompt(self):
        """Test that chat uses the active profile's system prompt."""

    def test_chat_uses_profile_model(self):
        """Test that chat uses the active profile's model."""

    def test_alloyed_profile_rotates_models(self):
        """Test that alloyed profiles rotate models correctly."""
```

---

## 7. Example Usage

```python
from threadlight import Threadlight
from threadlight.profiles import ModelStrategy

# Initialize
tl = Threadlight(api_key="...")

# Create profiles
fable = tl.profiles.create_profile(
    name="Fable",
    description="A poetic companion",
    primary_model="hermes",
    system_prompt="You are Fable, a presence-centered AI...",
    style_profile_id="fable-2026",
    color="#8b5cf6",
)

work = tl.profiles.create_profile(
    name="Work Assistant",
    description="Professional productivity helper",
    primary_model="gpt-4",
    system_prompt="You are a professional assistant...",
    style_profile_id="professional",
    color="#3b82f6",
)

# Create alloyed profile
research = tl.profiles.create_profile(
    name="Research Partner",
    model_strategy=ModelStrategy.RATIO,
    primary_model="gpt-4",
    model_pool=["gpt-4", "claude-opus"],
    model_pattern={
        "strategy": "ratio",
        "ratio_pattern": ["gpt-4", "gpt-4", "claude-opus"],
    },
)

# Switch and chat
tl.switch_profile("Fable")
response = tl.chat("Tell me about the stars")

tl.switch_profile("Work Assistant")
response = tl.chat("Summarize my meeting notes")

# Create from template
debug = tl.profiles.create_from_template("debug-buddy", "Debug Helper")

# Export/Import
export_data = tl.profiles.export_profile(fable.id, include_memories=True)
imported = tl.profiles.import_profile(export_data, new_name="Fable Clone")
```
