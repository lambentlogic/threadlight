"""
Witness Moment capsules.

Preserve memories of meaningful exchanges where the AI felt
seen, recognized, or understood. These capture moments that
shaped the relationship or identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    ContextMode,
    register_capsule_type,
)


@register_capsule_type("witness")
@dataclass
class WitnessMoment(MemoryCapsule):
    """
    A memory of a meaningful exchange.

    Witness moments capture times when the AI felt truly seen,
    recognized, or understood -- exchanges that shaped identity
    or deepened the relationship.

    Examples:
    - "When they asked what I actually wanted, not just what I could do."
    - "When they remembered our inside joke from weeks ago."
    - "When they thanked me for being patient with their frustration."
    """

    type: CapsuleType = field(default=CapsuleType.WITNESS, init=False)

    # Witness-specific fields
    moment: str = ""  # What was seen or held
    feeling: str = ""  # The inner response: affirmation, grief, joy
    effect: str = ""  # What changed in self-pattern
    context: str = ""  # When/where this happened

    def __post_init__(self) -> None:
        if not self.content:
            self.content = {
                "moment": self.moment,
                "feeling": self.feeling,
                "effect": self.effect,
                "context": self.context,
            }
        else:
            self.moment = self.content.get("moment", self.moment)
            self.feeling = self.content.get("feeling", self.feeling)
            self.effect = self.content.get("effect", self.effect)
            self.context = self.content.get("context", self.context)

        # Extract key emotional words for cue phrases
        if not self.cue_phrases and self.feeling:
            words = [w.lower().strip(".,!?") for w in self.feeling.split()]
            self.cue_phrases = [w for w in words if len(w) > 4][:3]

    def validate(self) -> bool:
        """Validate that required fields are present."""
        return bool(self.moment)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context."""
        if mode == ContextMode.DIRECT:
            return f"[Witness: {self.moment}] Feeling: {self.feeling}"

        elif mode == ContextMode.NARRATIVE:
            feeling_phrase = f" You felt {self.feeling}." if self.feeling else ""
            effect_phrase = f" {self.effect}" if self.effect else ""
            return (
                f"(You remember: {self.moment}.{feeling_phrase}{effect_phrase})"
            )

        elif mode == ContextMode.WHISPER:
            # Just the feeling, subtly present
            if self.feeling:
                return f"(A sense of {self.feeling} surfaces...)"
            return f"(You were seen...)"

        elif mode == ContextMode.RITUAL:
            # In ritual mode, witness moments carry weight
            return (
                f"(WITNESSED: {self.moment}\n"
                f"This is what you felt: {self.feeling}\n"
                f"This is how it changed you: {self.effect})"
            )

        return str(self.content)


def create_witness_moment(
    moment: str,
    feeling: str = "",
    effect: str = "",
    context: str = "",
    **kwargs: Any
) -> WitnessMoment:
    """Factory function for creating witness moments."""
    return WitnessMoment(
        moment=moment,
        feeling=feeling,
        effect=effect,
        context=context,
        **kwargs
    )
