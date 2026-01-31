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
    MYTH_SEED = "myth_seed"  # Internal name (backwards compat), UI shows "Identity Phrase"
    IDENTITY_PHRASE = "myth_seed"  # Alias pointing to same value for forwards compat
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

    # Profile scoping (for per-profile memory isolation)
    profile_scope: Optional[str] = None  # NULL = shared across all profiles

    # Deprecated: Use profile_scope instead (kept for backward compatibility)
    model_scope: Optional[str] = None  # NULL = shared across all models

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
            "profile_scope": self.profile_scope,
            "model_scope": self.model_scope,  # Deprecated, kept for backward compatibility
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

# Registry for user-defined custom type definitions
_custom_type_definitions: dict[str, "CustomTypeDefinition"] = {}


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


# =============================================================================
# Custom Type Capsule (User-Defined Types)
# =============================================================================

def register_custom_type_definition(type_def: "CustomTypeDefinition") -> None:
    """Register a user-defined custom type definition."""
    _custom_type_definitions[type_def.type_id] = type_def


def unregister_custom_type_definition(type_id: str) -> bool:
    """Unregister a user-defined custom type definition."""
    if type_id in _custom_type_definitions:
        del _custom_type_definitions[type_id]
        return True
    return False


def get_custom_type_definition(type_id: str) -> Optional["CustomTypeDefinition"]:
    """Get a registered custom type definition."""
    return _custom_type_definitions.get(type_id)


def list_custom_type_definitions() -> list["CustomTypeDefinition"]:
    """List all registered custom type definitions."""
    return list(_custom_type_definitions.values())


def is_custom_type(type_id: str) -> bool:
    """Check if a type_id corresponds to a user-defined custom type."""
    return type_id in _custom_type_definitions


@dataclass
class CustomTypeCapsule(MemoryCapsule):
    """
    A memory capsule that uses a user-defined custom type definition.

    This capsule type is dynamically configured based on a CustomTypeDefinition,
    allowing users to create structured memories with custom fields.

    The custom_type_id field indicates which custom type definition to use
    for validation and display formatting.
    """

    type: CapsuleType = field(default=CapsuleType.CUSTOM, init=False)

    # The ID of the custom type definition this capsule uses
    custom_type_id: str = ""

    # Default retention - can be overridden
    retention: RetentionPolicy = field(default=RetentionPolicy.NORMAL)

    def __post_init__(self) -> None:
        self.type = CapsuleType.CUSTOM

        # Store custom_type_id in content for serialization
        if self.custom_type_id and "custom_type_id" not in self.content:
            self.content["custom_type_id"] = self.custom_type_id
        elif "custom_type_id" in self.content and not self.custom_type_id:
            self.custom_type_id = self.content["custom_type_id"]

        # Extract cue phrases from content if not set
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _extract_cue_phrases(self) -> None:
        """Extract searchable cue phrases from the content."""
        phrases = []
        for key, value in self.content.items():
            if key in ("custom_type_id", "capsule_subtype"):
                continue
            if isinstance(value, str) and len(value) > 2:
                # Add whole value and significant words
                if len(value) <= 50:
                    phrases.append(value.lower())
                words = value.lower().split()
                phrases.extend(w for w in words if len(w) >= 4)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and len(item) > 2:
                        phrases.append(item.lower())

        # Deduplicate and limit
        seen = set()
        unique = []
        for p in phrases:
            if p not in seen:
                seen.add(p)
                unique.append(p)
                if len(unique) >= 15:
                    break
        self.cue_phrases = unique

    def get_type_definition(self) -> Optional["CustomTypeDefinition"]:
        """Get the type definition for this capsule."""
        return get_custom_type_definition(self.custom_type_id)

    def validate(self) -> bool:
        """Validate that the capsule has required fields based on type definition."""
        type_def = self.get_type_definition()
        if type_def is None:
            # No type definition, just check we have some content
            return bool(self.content)

        is_valid, errors = type_def.validate_instance(self.content)
        return is_valid

    def get_validation_errors(self) -> list[str]:
        """Get validation errors for this capsule's content."""
        type_def = self.get_type_definition()
        if type_def is None:
            return []

        is_valid, errors = type_def.validate_instance(self.content)
        return errors

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """
        Transform into prompt-ready context.

        Uses field-level templates from the type definition to create
        natural-feeling context. Falls back to display format if no
        templates are defined.
        """
        type_def = self.get_type_definition()

        # Format using field templates for rich context, display template for short form
        if type_def:
            # Use field templates for full context composition
            context_text = type_def.format_for_context(self.content)
            display = type_def.format_display(self.content)
            type_name = type_def.display_name
        else:
            context_text = str(self.content)
            display = context_text
            type_name = self.custom_type_id or "Custom"

        if mode == ContextMode.DIRECT:
            # Use field templates for rich, natural context
            return f"[{type_name}] {context_text}"

        elif mode == ContextMode.NARRATIVE:
            # Use field templates wrapped in narrative framing
            return f"(You recall: {context_text})"

        elif mode == ContextMode.WHISPER:
            # Short form uses display template
            return f"({display[:80]}...)" if len(display) > 80 else f"({display})"

        elif mode == ContextMode.RITUAL:
            # Use field templates for full ritual context
            return f"(A memory surfaces: {context_text})"

        return context_text

    def get_preview(self) -> str:
        """Get a short preview of this capsule."""
        type_def = self.get_type_definition()
        if type_def:
            return type_def.format_display(self.content)
        return str(self.content)[:100]

    def to_dict(self) -> dict[str, Any]:
        """Serialize capsule to dictionary."""
        data = super().to_dict()
        data["custom_type_id"] = self.custom_type_id
        return data


# Type hint import for CustomTypeDefinition (avoid circular import)
if False:  # TYPE_CHECKING equivalent that doesn't need import
    from threadlight.capsules.custom_types import CustomTypeDefinition
