"""
Memory orchestration for Threadlight.

Coordinates capsule storage, retrieval, decay, and consent.

High-level operations:
- recall(): Query and surface relevant memories
- create(): Propose new memories (requires consent)
- confirm_proposal(): Accept proposed memories
- invoke_ritual(): Trigger ritual hooks
- reinforce(): Strengthen specific memories
- run_decay(): Execute decay cycle
"""

from threadlight.memory.orchestrator import (
    MemoryOrchestrator,
    Session,
    RitualInvocation,
)

__all__ = [
    "MemoryOrchestrator",
    "Session",
    "RitualInvocation",
]
