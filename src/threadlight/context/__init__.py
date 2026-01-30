"""
Context composition for Threadlight.

Transforms retrieved memories into prompt-ready context.
This is where the "threadlight" happens -- memories become
tone-informed presence cues, not raw data dumps.

Composition Modes:
- DIRECT: Factual integration ("You know that...")
- NARRATIVE: Story-like framing ("You recall...")
- WHISPER: Subtle tone cues ("There is warmth when...")
- RITUAL: Full activation for command invocations

Soft Memory Modes:
- DISABLED: Don't include past conversation history
- RELEVANT: Include relevant past messages based on current message
- RECENT: Include recent messages from any conversation
"""

from threadlight.context.composer import (
    ContextComposer,
    ComposedContext,
    CompositionStrategy,
    SoftMemoryMode,
    estimate_tokens,
    compose_direct,
    compose_narrative,
    compose_whisper,
    compose_ritual,
)

from threadlight.context.soft_memory import (
    SoftMemory,
    SoftMemoryConfig,
    create_soft_memory,
)

__all__ = [
    "ContextComposer",
    "ComposedContext",
    "CompositionStrategy",
    "SoftMemoryMode",
    "estimate_tokens",
    "compose_direct",
    "compose_narrative",
    "compose_whisper",
    "compose_ritual",
    "SoftMemory",
    "SoftMemoryConfig",
    "create_soft_memory",
]
