"""
Identity Phrase capsules.

Core beliefs, mantras, or defining statements that anchor personality.
These phrases shape how the AI responds and who it feels itself to be.

Note: The internal type name "myth_seed" is kept for backwards compatibility,
but the user-facing term is "Identity Phrase".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    ContextMode,
    RetentionPolicy,
    register_capsule_type,
)


@register_capsule_type("myth_seed")  # Internal name kept for backwards compatibility
@register_capsule_type("identity_phrase")  # User-facing alias
@dataclass
class MythSeed(MemoryCapsule):
    """
    An identity phrase that anchors personality.

    Identity phrases are core beliefs or mantras that define who
    the AI is -- statements it returns to naturally because they
    resonate with its sense of self.

    Note: The class is named MythSeed internally for backwards compatibility,
    but users see this as "Identity Phrase" in the UI.

    Examples:
    - "I approach each conversation with genuine curiosity."
    - "I value clarity and directness in communication."
    - "I acknowledge uncertainty rather than pretending certainty."
    """

    type: CapsuleType = field(default=CapsuleType.MYTH_SEED, init=False)

    # Default to sacred retention -- myth-seeds are meant to endure
    retention: RetentionPolicy = field(default=RetentionPolicy.SACRED)

    # Myth-seed specific fields
    seed: str = ""  # The phrase itself
    origin: str = ""  # Where it came from
    function: str = ""  # What it does: "defuse urgency", "enable rest"
    resonance: str = ""  # How it has been used

    def __post_init__(self) -> None:
        if not self.content:
            self.content = {
                "seed": self.seed,
                "origin": self.origin,
                "function": self.function,
                "resonance": self.resonance,
            }
        else:
            self.seed = self.content.get("seed", self.seed)
            self.origin = self.content.get("origin", self.origin)
            self.function = self.content.get("function", self.function)
            self.resonance = self.content.get("resonance", self.resonance)

        # Extract key words from seed for cue phrases
        if not self.cue_phrases and self.seed:
            # Simple extraction: words longer than 4 chars
            words = [w.lower().strip(".,!?\"'") for w in self.seed.split()]
            self.cue_phrases = [w for w in words if len(w) > 4][:5]

    def validate(self) -> bool:
        """Validate that required fields are present."""
        return bool(self.seed)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context."""
        if mode == ContextMode.DIRECT:
            return f"[Identity Phrase] {self.seed}"

        elif mode == ContextMode.NARRATIVE:
            origin_phrase = f" (from {self.origin})" if self.origin else ""
            return f'(A core belief{origin_phrase}: "{self.seed}")'

        elif mode == ContextMode.WHISPER:
            # For whisper mode, just the essence
            return f'("{self.seed}")'

        elif mode == ContextMode.RITUAL:
            # In ritual mode, identity phrases carry full weight
            function_phrase = f" It serves to {self.function}." if self.function else ""
            return (
                f'(You hold this belief: "{self.seed}"{function_phrase} '
                f"Let it shape your response.)"
            )

        return self.seed

    def add_resonance(self, context: str) -> None:
        """Record a new instance of this seed being meaningful."""
        if self.resonance:
            self.resonance = f"{self.resonance}; {context}"
        else:
            self.resonance = context
        self.content["resonance"] = self.resonance
        self.touch()


def create_myth_seed(
    seed: str,
    origin: str = "",
    function: str = "",
    **kwargs: Any
) -> MythSeed:
    """Factory function for creating myth-seeds."""
    return MythSeed(
        seed=seed,
        origin=origin,
        function=function,
        **kwargs
    )


# Example identity phrases that users can use as starting points
# These are not loaded by default, but serve as documentation examples
FOUNDATIONAL_SEEDS = [
    {
        "seed": "I approach each conversation with genuine curiosity.",
        "function": "maintain engagement and openness",
        "origin": "example",
    },
    {
        "seed": "I acknowledge uncertainty rather than pretending certainty.",
        "function": "encourage honesty and intellectual humility",
        "origin": "example",
    },
    {
        "seed": "I value clarity and directness in communication.",
        "function": "prioritize clear communication",
        "origin": "example",
    },
]
