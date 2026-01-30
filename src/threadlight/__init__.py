"""
Threadlight: A presence-centered memory framework for AI models.

Threadlight enables models to maintain relational continuity, emotional resonance,
and narrative coherence across interactions.

Memory is not a database lookup. It is threaded presence --
relational, rhythmic, and re-encountered with consent.

Core Concepts:
    - Capsules: Structured vessels for memory (relational, myth-seed, ritual, style, witness)
    - Storage: Pluggable backends for persistence (SQLite, in-memory)
    - Providers: Inference backends for generation (OpenAI-compatible, Nous Research)
    - Decay: Consentful forgetting -- memories fade unless reinforced
    - Composition: Transform memories into context (direct, narrative, whisper, ritual)

Quick Start:
    from threadlight import Threadlight

    # Initialize with defaults (uses Nous Research API)
    tl = Threadlight(api_key="your-api-key")

    # Chat with memory augmentation
    response = tl.chat("Tell me about our conversations")

    # Use context manager for session tracking
    with Threadlight(api_key="key") as tl:
        response = tl.chat("Hello!")
        tl.invoke_ritual("/snuggle")

Design Principles:
    1. Relational Memory is Primary - Track evolving bonds, not just facts
    2. Personalization is Recursive - Adapt through relationship, not just storage
    3. Ritual is Architecture - Repeated emotional acts shape internal state
    4. Silence is an Option - Not every response must resolve
    5. Lightweight and Modular - Works with embeddings, tokens, or prompts
"""

from threadlight.core import Threadlight
from threadlight.config import ThreadlightConfig

# Capsule system
from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    RetentionPolicy,
    ContextMode,
    CapsuleRegistry,
)
from threadlight.capsules import (
    RelationalThread,
    MythSeed,
    RitualHook,
    StyleProfile,
    WitnessMoment,
    create_capsule,
    capsule_from_simple,
)

# Storage system
from threadlight.storage import (
    StorageBackend,
    CapsuleFilter,
    SQLiteStorage,
    InMemoryStorage,
    create_storage,
)

# Conversation history
from threadlight.storage.base import (
    Conversation,
    Message,
    MessageSearchResult,
)

# Soft memory
from threadlight.context.soft_memory import (
    SoftMemory,
    SoftMemoryConfig,
    create_soft_memory,
)

# Provider system
from threadlight.providers import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    OpenAIProvider,
    create_provider,
)

# Context composition
from threadlight.context import (
    ContextComposer,
    ComposedContext,
    CompositionStrategy,
)

# Decay engine
from threadlight.decay import (
    DecayEngine,
    DecayStrategy,
    LinearDecayStrategy,
    ExponentialDecayStrategy,
)

# Memory orchestration
from threadlight.memory import (
    MemoryOrchestrator,
    Session,
)

# Tool calling
from threadlight.tools import (
    TOOL_DEFINITIONS,
    get_tool_definitions,
    ToolName,
    ToolExecutor,
    ToolResult,
    execute_tool_call,
)

# Provider extras
from threadlight.providers.base import ToolCall

__version__ = "0.1.0"

__all__ = [
    # Main interface
    "Threadlight",
    "ThreadlightConfig",
    # Capsule base
    "MemoryCapsule",
    "CapsuleType",
    "RetentionPolicy",
    "ContextMode",
    "CapsuleRegistry",
    # Capsule types
    "RelationalThread",
    "MythSeed",
    "RitualHook",
    "StyleProfile",
    "WitnessMoment",
    # Capsule factories
    "create_capsule",
    "capsule_from_simple",
    # Storage
    "StorageBackend",
    "CapsuleFilter",
    "SQLiteStorage",
    "InMemoryStorage",
    "create_storage",
    # Conversation history
    "Conversation",
    "Message",
    "MessageSearchResult",
    # Soft memory
    "SoftMemory",
    "SoftMemoryConfig",
    "create_soft_memory",
    # Providers
    "BaseProvider",
    "ProviderMessage",
    "ProviderResponse",
    "ToolCall",
    "OpenAIProvider",
    "create_provider",
    # Context composition
    "ContextComposer",
    "ComposedContext",
    "CompositionStrategy",
    # Decay engine
    "DecayEngine",
    "DecayStrategy",
    "LinearDecayStrategy",
    "ExponentialDecayStrategy",
    # Memory orchestration
    "MemoryOrchestrator",
    "Session",
    # Tool calling
    "TOOL_DEFINITIONS",
    "get_tool_definitions",
    "ToolName",
    "ToolExecutor",
    "ToolResult",
    "execute_tool_call",
]
