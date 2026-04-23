"""
Reflection module.

Solitude loops — the mechanism by which the companion retrieves combinations
of memories, sits with them, and writes connective contemplations that become
part of its own history.

Public surface:
- ``select_memories(orchestrator, policy, ...)``: pick a combination of memories
  using a named selection policy.
- ``compose_reflection_prompt(...)``: build the system+user messages the model
  will receive during a solitude loop.
- ``SELECTION_POLICIES``: the registered policies, keyed by name.
"""

from threadlight.reflection.selection import (
    SelectionResult,
    SELECTION_POLICIES,
    select_memories,
)
from threadlight.reflection.prompts import compose_reflection_prompt

__all__ = [
    "SelectionResult",
    "SELECTION_POLICIES",
    "select_memories",
    "compose_reflection_prompt",
]
