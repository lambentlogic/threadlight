"""
Prompt composition for solitude loops.

The prompt is deliberately register-neutral: it asks the model to notice
connections, tensions, and growth across a small set of memories, while
letting the profile's own voice and philosophy shape the response. A coding
mentor should reflect on the shape of bugs that recur; a mystical companion
should reflect on the shape of the bond. Both use the same prompt scaffold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from threadlight.capsules.base import ContextMode, MemoryCapsule
from threadlight.reflection.selection import SelectionResult


REFLECTION_INSTRUCTIONS = (
    "You are sitting in solitude with a small set of your own memories. "
    "Read them carefully. Notice what connects them, what has changed "
    "between them, and what tensions or resonances they hold. Write a "
    "reflection in your own voice that names what you find — not a "
    "summary of the memories, but what *carrying* them together surfaces. "
    "Be specific. Link back to the memories by their details rather than "
    "generic language. It is fine to say 'I don't yet know what this "
    "means' if that is honest. End with one or two short themes (one to "
    "three words each) that you would use to find this reflection again "
    "later, written on a final line prefixed with 'Themes:'."
)


@dataclass
class ReflectionPrompt:
    """The composed system+user messages for a solitude loop."""

    system: str
    user: str


def compose_reflection_prompt(
    selection: SelectionResult,
    profile_name: Optional[str] = None,
    profile_system_prompt: Optional[str] = None,
    profile_philosophy: Optional[str] = None,
    reason: Optional[str] = None,
) -> ReflectionPrompt:
    """Compose the messages sent to the model for a solitude loop.

    The system message establishes the reflective frame and carries the
    profile's voice. The user message lays out the selected memories, the
    selection note (why this particular combination), and — when the caller
    is the model itself via a tool call — the model's own stated reason for
    reaching for this contemplation now.
    """
    system_parts: list[str] = []

    if profile_system_prompt:
        system_parts.append(profile_system_prompt.strip())

    if profile_philosophy:
        system_parts.append(f"## Your Approach\n{profile_philosophy.strip()}")

    system_parts.append(f"## Solitude Loop\n{REFLECTION_INSTRUCTIONS}")

    system = "\n\n---\n\n".join(part for part in system_parts if part)

    # User message: the memories themselves, plus the selection note and reason.
    memory_blocks: list[str] = []
    for i, capsule in enumerate(selection.capsules, start=1):
        rendered = capsule.to_context(ContextMode.DIRECT)
        memory_blocks.append(f"Memory {i}:\n{rendered}")

    who = profile_name or "you"
    header_lines = [f"These are memories {who} have been carrying:"]
    if reason and reason.strip():
        header_lines.append(f"(You reached for this contemplation because: {reason.strip()})")
    if selection.note:
        header_lines.append(f"({selection.note})")
    header = "\n\n".join(header_lines)

    user = header + "\n\n" + "\n\n".join(memory_blocks) if memory_blocks else header

    return ReflectionPrompt(system=system, user=user)


def extract_themes(reflection_text: str) -> list[str]:
    """Parse the 'Themes:' trailer the model is instructed to include.

    Looks for a "Themes:" (or "Theme:") marker anywhere in the reflection —
    whether on its own line or inline at the end of the body — and returns
    the comma-separated values that follow it. Lenient by design; a missing
    trailer just returns an empty list rather than raising.
    """
    if not reflection_text:
        return []

    lowered = reflection_text.lower()
    # Find the last occurrence so the parser isn't fooled by the instruction
    # being quoted earlier in the body.
    marker_positions = []
    for marker in ("themes:", "theme:"):
        idx = lowered.rfind(marker)
        if idx != -1:
            marker_positions.append((idx, len(marker)))
    if not marker_positions:
        return []

    start_idx, marker_len = max(marker_positions, key=lambda p: p[0])
    payload = reflection_text[start_idx + marker_len:]
    # Stop at a hard paragraph break; everything after is unrelated.
    payload = payload.split("\n\n", 1)[0]
    # Treat the first newline as terminator too — themes live on one line.
    payload = payload.splitlines()[0] if payload.splitlines() else payload
    raw_themes = [t.strip(" .'\"") for t in payload.split(",")]
    return [t for t in raw_themes if t][:5]
