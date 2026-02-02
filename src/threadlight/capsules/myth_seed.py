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
        # Restore structured fields from content if loading from storage
        if self.content:
            self.seed = self.content.get("seed", self.seed)
            self.origin = self.content.get("origin", self.origin)
            self.function = self.content.get("function", self.function)
            self.resonance = self.content.get("resonance", self.resonance)
            # Restore text from content if present (loading from storage)
            if self.text is None and "text" in self.content:
                self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate it from structured fields
        if self.text is None and self.seed:
            self.text = self._generate_text_from_fields()

        # Always sync structured fields to content dict for storage/serialization
        self.content = {
            "seed": self.seed,
            "origin": self.origin,
            "function": self.function,
            "resonance": self.resonance,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Extract cue phrases
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _generate_text_from_fields(self) -> str:
        """Generate natural narrative text from structured fields.

        Creates a readable narrative that presents the identity phrase
        in a way that feels meaningful and anchoring.
        """
        parts = []

        # The seed itself is the core - present it as a belief
        if self.seed:
            parts.append(f'"{self.seed}"')

        # Add what it does (function)
        if self.function:
            parts.append(f"This helps me {self.function}.")

        # Add origin if available
        if self.origin:
            parts.append(f"(From {self.origin}.)")

        return " ".join(parts) if parts else ""

    def _extract_cue_phrases(self) -> None:
        """Extract key words for cue phrases from text or seed."""
        source = self.text if self.text else self.seed
        if source:
            words = [w.lower().strip(".,!?\"'") for w in source.split()]
            self.cue_phrases = [w for w in words if len(w) > 4][:5]

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR seed (for backward compatibility).
        """
        return bool(self.text or self.seed)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context.

        Text-first: When text field exists, use it directly instead of
        reconstructing from structured fields. Falls back to field-based
        construction for backward compatibility with memories that don't
        have a text field.
        """
        if mode == ContextMode.DIRECT:
            # If we have text, use it directly
            if self.text:
                return f"[Identity Phrase] {self.text}"
            # Fallback: use seed
            return f"[Identity Phrase] {self.seed}"

        elif mode == ContextMode.NARRATIVE:
            # If we have text, wrap it in narrative framing
            if self.text:
                return f"(A core belief: {self.text})"
            # Fallback: reconstruct from fields
            origin_phrase = f" (from {self.origin})" if self.origin else ""
            return f'(A core belief{origin_phrase}: "{self.seed}")'

        elif mode == ContextMode.WHISPER:
            # For whisper mode, just the essence
            if self.text:
                # Try to extract just the quote if present
                if '"' in self.text:
                    # Extract the quoted part
                    start = self.text.find('"')
                    end = self.text.find('"', start + 1)
                    if end > start:
                        return f'({self.text[start:end+1]})'
                return f'("{self.text[:50]}...")'
            return f'("{self.seed}")'

        elif mode == ContextMode.RITUAL:
            # In ritual mode, identity phrases carry full weight
            if self.text:
                return (
                    f"(You hold this belief: {self.text} "
                    f"Let it shape your response.)"
                )
            # Fallback: reconstruct from fields
            function_phrase = f" It serves to {self.function}." if self.function else ""
            return (
                f'(You hold this belief: "{self.seed}"{function_phrase} '
                f"Let it shape your response.)"
            )

        return self.text if self.text else self.seed

    def add_resonance(self, context: str) -> None:
        """Record a new instance of this seed being meaningful."""
        if self.resonance:
            self.resonance = f"{self.resonance}; {context}"
        else:
            self.resonance = context
        self.content["resonance"] = self.resonance
        # Keep text in sync if it exists
        if self.text:
            self.content["text"] = self.text
        self.touch()


def create_myth_seed(
    seed: str = "",
    origin: str = "",
    function: str = "",
    text: str | None = None,
    **kwargs: Any
) -> MythSeed:
    """Factory function for creating myth-seeds (identity phrases).

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. Structured fields remain for search/organization but
    text takes precedence for context composition.

    Args:
        seed: The identity phrase itself (e.g., "I approach each conversation with curiosity")
        origin: Where this phrase came from
        function: What it does (e.g., "defuse urgency", "enable rest")
        text: Primary narrative content (optional). If provided, this is
              the main text that will be used for context composition.
              If not provided, text will be generated from structured fields.
    """
    return MythSeed(
        seed=seed,
        origin=origin,
        function=function,
        text=text,
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
