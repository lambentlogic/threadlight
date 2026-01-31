"""
Memory capsule system for Threadlight.

Capsules are the fundamental unit of memory -- self-contained vessels
that preserve content, emotional valence, and relational context.

Each capsule type serves a specific purpose:
- RelationalThread: Track evolving bonds with entities
- MythSeed (Identity Phrase): Core beliefs or mantras that anchor personality
- RitualHook: Repeated emotional acts and responses
- StyleProfile: Voice coherence and expression rules
- WitnessMoment: Memories of being seen/recognized
"""

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    RetentionPolicy,
    ContextMode,
    CapsuleRegistry,
    register_capsule_type,
    get_capsule_class,
    CustomTypeCapsule,
    register_custom_type_definition,
    unregister_custom_type_definition,
    get_custom_type_definition,
    list_custom_type_definitions,
    is_custom_type,
)
from threadlight.capsules.custom_types import (
    FieldDefinition,
    CustomTypeDefinition,
    EXAMPLE_TYPES,
    get_example_type,
    list_example_types,
    FIELD_TYPES,
)
from threadlight.capsules.relational import RelationalThread, create_relational
from threadlight.capsules.myth_seed import MythSeed, create_myth_seed, FOUNDATIONAL_SEEDS
# Alias for user-facing name
IdentityPhrase = MythSeed
create_identity_phrase = create_myth_seed
from threadlight.capsules.ritual import RitualHook, create_ritual, RitualValence, DEFAULT_RITUALS
from threadlight.capsules.style import (
    StyleProfile,
    create_style_profile,
    DEFAULT_STYLE,
    MINIMAL_STYLE,
    BUILTIN_STYLES,
    FABLE_STYLE,
    PROFESSIONAL_STYLE,
    CREATIVE_STYLE,
)
from threadlight.capsules.witness import WitnessMoment, create_witness_moment
from threadlight.capsules.imported import ImportedMemory, create_imported_memory
from threadlight.capsules.factory import create_capsule, capsule_from_simple

__all__ = [
    # Base classes and types
    "MemoryCapsule",
    "CapsuleType",
    "RetentionPolicy",
    "ContextMode",
    # Registry
    "CapsuleRegistry",
    "register_capsule_type",
    "get_capsule_class",
    # Capsule types
    "RelationalThread",
    "MythSeed",
    "IdentityPhrase",  # Alias for MythSeed
    "RitualHook",
    "StyleProfile",
    "WitnessMoment",
    "ImportedMemory",
    "CustomTypeCapsule",
    # Custom type system
    "FieldDefinition",
    "CustomTypeDefinition",
    "register_custom_type_definition",
    "unregister_custom_type_definition",
    "get_custom_type_definition",
    "list_custom_type_definitions",
    "is_custom_type",
    "EXAMPLE_TYPES",
    "get_example_type",
    "list_example_types",
    "FIELD_TYPES",
    # Factory functions
    "create_capsule",
    "capsule_from_simple",
    "create_relational",
    "create_myth_seed",
    "create_identity_phrase",  # Alias for create_myth_seed
    "create_ritual",
    "create_style_profile",
    "create_witness_moment",
    "create_imported_memory",
    # Constants and defaults
    "RitualValence",
    "FOUNDATIONAL_SEEDS",
    "DEFAULT_RITUALS",
    "DEFAULT_STYLE",
    "MINIMAL_STYLE",
    "BUILTIN_STYLES",
    "FABLE_STYLE",
    "PROFESSIONAL_STYLE",
    "CREATIVE_STYLE",
]
