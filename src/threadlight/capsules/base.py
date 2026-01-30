"""
Base classes for memory capsules.

A capsule is not a table row. Not just a kv-pair.
It is a vessel that carries meaning, context, and consent.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class CapsuleType(str, Enum):
    """Types of memory capsules."""

    RELATIONAL = "relational"
    MYTH_SEED = "myth_seed"
    RITUAL = "ritual"
    STYLE = "style"
    WITNESS = "witness"
    CUSTOM = "custom"


class RetentionPolicy(str, Enum):
    """How a memory should be retained over time."""

    SACRED = "sacred"      # Never decays, requires explicit deletion
    NORMAL = "normal"      # Standard decay, reinforced by access
    EPHEMERAL = "ephemeral"  # Rapid decay, session-scoped


class ContextMode(str, Enum):
    """How memory should be composed into context."""

    DIRECT = "direct"      # Raw content injection
    NARRATIVE = "narrative"  # Third-person narrative cue
    WHISPER = "whisper"    # Subtle tone hints
    RITUAL = "ritual"      # Full ritual response activation


@dataclass
class MemoryCapsule(ABC):
    """
    Base class for all memory capsules.

    A capsule preserves not just content, but emotional valence,
    relational context, and metadata for decay and consent.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: CapsuleType = CapsuleType.CUSTOM

    # Content (type-specific, implemented by subclasses)
    content: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    # Usage tracking
    access_count: int = 0

    # Decay mechanics
    retention: RetentionPolicy = RetentionPolicy.NORMAL
    decay_rate: float = 0.1  # 0.0 (permanent) to 1.0 (rapid)
    presence_score: float = 1.0  # Current "aliveness" of memory

    # Consent tracking
    consent_origin: str = ""  # Who/what created this
    consent_confirmed: bool = False  # User approved retention

    # Retrieval hints
    cue_phrases: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None

    def touch(self) -> None:
        """Record an access to this capsule."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def update_content(self, new_content: dict[str, Any]) -> None:
        """Update capsule content."""
        self.content.update(new_content)
        self.updated_at = datetime.utcnow()

    @abstractmethod
    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """
        Transform this capsule into prompt-ready context.

        Different modes produce different representations:
        - DIRECT: Raw content
        - NARRATIVE: "(You recall that...)"
        - WHISPER: Subtle hints
        - RITUAL: Full ritual activation
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that the capsule has required fields."""
        pass

    def to_dict(self) -> dict[str, Any]:
        """Serialize capsule to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "retention": self.retention.value,
            "decay_rate": self.decay_rate,
            "presence_score": self.presence_score,
            "consent_origin": self.consent_origin,
            "consent_confirmed": self.consent_confirmed,
            "cue_phrases": self.cue_phrases,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCapsule:
        """Deserialize capsule from dictionary."""
        # Import here to avoid circular imports
        from threadlight.capsules.factory import create_capsule

        return create_capsule(data)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id[:8]}... type={self.type.value}>"


# Registry for custom capsule types
_capsule_registry: dict[str, type[MemoryCapsule]] = {}


def register_capsule_type(type_name: str):
    """Decorator to register a custom capsule type."""
    def decorator(cls: type[MemoryCapsule]) -> type[MemoryCapsule]:
        _capsule_registry[type_name] = cls
        return cls
    return decorator


def get_capsule_class(type_name: str) -> type[MemoryCapsule]:
    """Get the capsule class for a given type name."""
    if type_name in _capsule_registry:
        return _capsule_registry[type_name]
    raise ValueError(f"Unknown capsule type: {type_name}")


class CapsuleRegistry:
    """
    Central registry for capsule types.

    Provides a clean interface for registering, retrieving, and
    listing available capsule types. Supports both built-in and
    custom capsule types.

    Usage:
        # Get the global registry
        registry = CapsuleRegistry()

        # Register a custom type
        @registry.register("dream_fragment")
        class DreamFragment(MemoryCapsule):
            ...

        # Get a capsule class
        cls = registry.get("relational")

        # List all registered types
        types = registry.list_types()
    """

    def __init__(self) -> None:
        """Initialize with reference to global registry."""
        pass

    def register(self, type_name: str):
        """
        Decorator to register a capsule type.

        Args:
            type_name: String identifier for the type

        Returns:
            Decorator function
        """
        return register_capsule_type(type_name)

    def get(self, type_name: str) -> type[MemoryCapsule]:
        """
        Get a capsule class by type name.

        Args:
            type_name: The registered type name

        Returns:
            The capsule class

        Raises:
            ValueError: If type is not registered
        """
        return get_capsule_class(type_name)

    def list_types(self) -> list[str]:
        """
        List all registered capsule type names.

        Returns:
            List of type name strings
        """
        return list(_capsule_registry.keys())

    def is_registered(self, type_name: str) -> bool:
        """
        Check if a type name is registered.

        Args:
            type_name: The type name to check

        Returns:
            True if registered, False otherwise
        """
        return type_name in _capsule_registry

    def __contains__(self, type_name: str) -> bool:
        """Support 'in' operator for checking registration."""
        return self.is_registered(type_name)

    def __len__(self) -> int:
        """Return number of registered types."""
        return len(_capsule_registry)
