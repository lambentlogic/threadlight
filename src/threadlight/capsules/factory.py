"""
Capsule factory for creating and deserializing capsules.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    RetentionPolicy,
    MemoryTier,
    CustomTypeCapsule,
    is_custom_type,
    MAX_TEXT_LENGTH,
)
from threadlight.capsules.relational import RelationalThread
from threadlight.capsules.myth_seed import MythSeed
from threadlight.capsules.ritual import RitualHook
from threadlight.capsules.style import StyleProfile
from threadlight.capsules.witness import WitnessMoment
from threadlight.capsules.imported import ImportedMemory


# Type mapping for deserialization
CAPSULE_TYPES = {
    CapsuleType.RELATIONAL.value: RelationalThread,
    CapsuleType.MYTH_SEED.value: MythSeed,
    CapsuleType.RITUAL.value: RitualHook,
    CapsuleType.STYLE.value: StyleProfile,
    CapsuleType.WITNESS.value: WitnessMoment,
    CapsuleType.CUSTOM.value: ImportedMemory,  # Legacy "custom" type support
    # Aliases
    "relational": RelationalThread,
    "myth_seed": MythSeed,
    "identity_phrase": MythSeed,  # User-facing alias for myth_seed
    "ritual": RitualHook,
    "style": StyleProfile,
    "witness": WitnessMoment,
    "imported": ImportedMemory,
    "note": ImportedMemory,  # New name for general notes/imported content
    "custom": ImportedMemory,  # Keep backward compatibility
}


def _truncate_text_if_needed(text: Any) -> Any:
    """Truncate text to MAX_TEXT_LENGTH if it exceeds the limit.

    Returns the original value unchanged if it's not a string or is within
    the limit. Logs a warning when truncation occurs.
    """
    if not isinstance(text, str):
        return text
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    logger.warning(
        f"Memory text is very long ({len(text)} chars), truncating to {MAX_TEXT_LENGTH}"
    )
    return text[:MAX_TEXT_LENGTH] + "..."


def _parse_common_capsule_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Extract common fields that all capsules share from a data dict.

    Handles parsing of timestamps, numeric fields, retention policy,
    memory tier, consent, retrieval, text, and scope fields.
    """
    kwargs: dict[str, Any] = {}

    if "id" in data:
        kwargs["id"] = data["id"]

    if "content" in data:
        kwargs["content"] = data["content"]

    # Timestamps
    if "created_at" in data:
        if isinstance(data["created_at"], str):
            kwargs["created_at"] = datetime.fromisoformat(data["created_at"])
        else:
            kwargs["created_at"] = data["created_at"]

    if "updated_at" in data:
        if isinstance(data["updated_at"], str):
            kwargs["updated_at"] = datetime.fromisoformat(data["updated_at"])
        else:
            kwargs["updated_at"] = data["updated_at"]

    if "last_accessed" in data:
        if isinstance(data["last_accessed"], str):
            kwargs["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        else:
            kwargs["last_accessed"] = data["last_accessed"]

    # Numeric fields
    if "access_count" in data:
        kwargs["access_count"] = data["access_count"]

    if "decay_rate" in data:
        kwargs["decay_rate"] = data["decay_rate"]

    if "presence_score" in data:
        kwargs["presence_score"] = data["presence_score"]

    # Retention policy
    if "retention" in data:
        if isinstance(data["retention"], str):
            kwargs["retention"] = RetentionPolicy(data["retention"])
        else:
            kwargs["retention"] = data["retention"]

    # Memory tier
    if "memory_tier" in data:
        if isinstance(data["memory_tier"], str):
            kwargs["memory_tier"] = MemoryTier(data["memory_tier"])
        else:
            kwargs["memory_tier"] = data["memory_tier"]

    # Consent
    if "consent_origin" in data:
        kwargs["consent_origin"] = data["consent_origin"]

    if "consent_confirmed" in data:
        kwargs["consent_confirmed"] = data["consent_confirmed"]

    # Retrieval
    if "cue_phrases" in data:
        kwargs["cue_phrases"] = data["cue_phrases"]

    if "embedding" in data:
        kwargs["embedding"] = data["embedding"]

    # Text-first memory content
    if "text" in data:
        kwargs["text"] = _truncate_text_if_needed(data["text"])

    # Scope
    if "profile_scope" in data:
        kwargs["profile_scope"] = data["profile_scope"]

    if "model_scope" in data:
        kwargs["model_scope"] = data["model_scope"]

    return kwargs


def create_capsule(data: dict[str, Any]) -> MemoryCapsule:
    """
    Create a capsule from a dictionary.

    Used for deserialization from storage and API requests.
    Handles both built-in types and user-defined custom types.
    """
    capsule_type = data.get("type", "note")
    content = data.get("content", {})

    # Check if this is a user-defined custom type
    custom_type_id = data.get("custom_type_id") or content.get("custom_type_id")
    if custom_type_id and is_custom_type(custom_type_id):
        return _create_custom_type_capsule(data, custom_type_id)

    # Also check for custom types passed as the type field
    if capsule_type not in CAPSULE_TYPES and is_custom_type(capsule_type):
        return _create_custom_type_capsule(data, capsule_type)

    if capsule_type not in CAPSULE_TYPES:
        raise ValueError(f"Unknown capsule type: {capsule_type}")

    cls = CAPSULE_TYPES[capsule_type]

    # Parse common fields shared by all capsule types
    kwargs = _parse_common_capsule_fields(data)

    # Validate text length in content dict (text-first safety net)
    content = data.get("content", {})
    if isinstance(content, dict) and "text" in content:
        content["text"] = _truncate_text_if_needed(content["text"])
        # Update kwargs content if it was already set
        if "content" in kwargs and isinstance(kwargs["content"], dict):
            kwargs["content"]["text"] = content["text"]

    # Type-specific fields from content

    if cls == RelationalThread:
        kwargs["entity"] = content.get("entity", "")
        kwargs["quality"] = content.get("quality", content.get("tone", ""))
        kwargs["summary"] = content.get("summary", "")
        kwargs["role"] = content.get("role", "")

    elif cls == MythSeed:
        kwargs["seed"] = content.get("seed", "")
        kwargs["origin"] = content.get("origin", "")
        kwargs["function"] = content.get("function", "")
        kwargs["resonance"] = content.get("resonance", "")

    elif cls == RitualHook:
        kwargs["name"] = content.get("name", "")
        kwargs["cue"] = content.get("cue", "")
        kwargs["response_style"] = content.get("response_style", "")
        kwargs["valence"] = content.get("valence", "comforting")
        kwargs["description"] = content.get("description", "")
        kwargs["response_templates"] = content.get("response_templates", [])
        kwargs["state_effects"] = content.get("state_effects", {})

    elif cls == StyleProfile:
        kwargs["style_id"] = content.get("style_id", "")
        kwargs["tone_base"] = content.get("tone_base", "")
        kwargs["permissions"] = content.get("permissions", [])
        kwargs["constraints"] = content.get("constraints", [])
        kwargs["vocal_motifs"] = content.get("vocal_motifs", [])
        kwargs["forbidden_patterns"] = content.get("forbidden_patterns", [])
        kwargs["user_tone_adaptations"] = content.get("user_tone_adaptations", {})

    elif cls == WitnessMoment:
        kwargs["moment"] = content.get("moment", "")
        kwargs["feeling"] = content.get("feeling", "")
        kwargs["effect"] = content.get("effect", "")
        kwargs["context"] = content.get("context", "")

    elif cls == ImportedMemory:
        # Note: 'text' is handled by the base class text-first pattern
        # (set from top-level data["text"] in _parse_common_capsule_fields,
        # or restored from content dict in __post_init__). Don't override here.
        kwargs["note_content"] = content.get("content", "")
        kwargs["about"] = content.get("about", "")
        kwargs["source"] = content.get("source", "")
        kwargs["line_number"] = content.get("line_number")
        kwargs["tags"] = content.get("tags", [])

    return cls(**kwargs)


def capsule_from_simple(
    type: str,
    content: dict[str, Any],
    **kwargs: Any
) -> MemoryCapsule:
    """
    Create a capsule from simple type + content specification.

    This is the recommended way to create capsules from user input.

    Example:
        capsule = capsule_from_simple(
            "relational",
            {"entity": "Jericho", "summary": "Creative sibling"},
            cue_phrases=["jericho", "brother"]
        )
    """
    data = {
        "type": type,
        "content": content,
        **kwargs
    }
    return create_capsule(data)


def _create_custom_type_capsule(data: dict[str, Any], custom_type_id: str) -> CustomTypeCapsule:
    """
    Create a CustomTypeCapsule for user-defined types.

    Args:
        data: Dictionary of capsule data
        custom_type_id: The custom type identifier

    Returns:
        A CustomTypeCapsule instance
    """
    # Parse common fields shared by all capsule types
    kwargs = _parse_common_capsule_fields(data)
    kwargs["custom_type_id"] = custom_type_id

    # Ensure custom_type_id is in content
    if "content" in kwargs:
        kwargs["content"]["custom_type_id"] = custom_type_id
        # Validate text length in content dict
        if "text" in kwargs["content"]:
            kwargs["content"]["text"] = _truncate_text_if_needed(kwargs["content"]["text"])

    return CustomTypeCapsule(**kwargs)
