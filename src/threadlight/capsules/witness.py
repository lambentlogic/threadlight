"""
Witness Moment capsules.

Preserve memories of witnessing - moments of being seen or of seeing another.
These capture exchanges that shaped relationship or identity, whether the AI
was witnessed, or witnessed another (human or AI).
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
    A memory of witnessing - being seen or seeing another.

    Witness moments are bidirectional: they capture times when the AI
    was witnessed (felt seen, recognized, understood) OR when the AI
    witnessed another being (held space, observed depth, recognized).

    The "other" can be human, AI, character, or whatever else.
    """

    type: CapsuleType = field(default=CapsuleType.WITNESS, init=False)

    # Witness-specific fields
    moment: str = ""  # What happened (language naturally indicates direction)
    feeling: str = ""  # The inner response: affirmation, grief, joy, awe
    effect: str = ""  # What changed or deepened
    context: str = ""  # When/where this happened
    entity: str = ""  # Who was involved (optional)

    def __post_init__(self) -> None:
        # Restore structured fields from content if loading from storage
        if self.content:
            self.moment = self.content.get("moment", self.moment)
            self.feeling = self.content.get("feeling", self.feeling)
            self.effect = self.content.get("effect", self.effect)
            self.context = self.content.get("context", self.context)
            self.entity = self.content.get("entity", self.entity)
            # Restore text from content if present (loading from storage)
            # Check _original_text first (richer narrative), then text
            if self.text is None:
                if "_original_text" in self.content:
                    self.text = self.content["_original_text"]
                elif "text" in self.content:
                    self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate it from structured fields
        if self.text is None and self.moment:
            self.text = self._generate_text_from_fields()

        # Always sync structured fields to content dict for storage/serialization
        self.content = {
            "moment": self.moment,
            "feeling": self.feeling,
            "effect": self.effect,
            "context": self.context,
            "entity": self.entity,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Extract key emotional words for cue phrases
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _generate_text_from_fields(self) -> str:
        """Generate natural narrative text from structured fields.

        Creates a readable narrative that preserves the meaning of the
        structured data while feeling natural and voice-preserving.
        """
        parts = []

        # Start with the moment - this is the core
        if self.moment:
            parts.append(f"I witnessed {self.moment}.")

        # Add the feeling as an inner response
        if self.feeling:
            parts.append(f"I felt {self.feeling}.")

        # Add the effect as what changed
        if self.effect:
            # Effect might already be a complete sentence
            effect_text = self.effect
            if not effect_text.endswith((".", "!", "?")):
                effect_text += "."
            parts.append(effect_text)

        return " ".join(parts)

    def _extract_cue_phrases(self) -> None:
        """Extract key words for cue phrases from text or feeling field."""
        source = self.text if self.text else self.feeling
        if source:
            words = [w.lower().strip(".,!?") for w in source.split()]
            self.cue_phrases = [w for w in words if len(w) > 4][:5]

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR moment (for backward compatibility).
        """
        return bool(self.text or self.moment)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context.

        Text-first: When text field exists, use it directly instead of
        reconstructing from structured fields. Falls back to field-based
        construction for backward compatibility with memories that don't
        have a text field.
        """
        if mode == ContextMode.DIRECT:
            # If we have text, use it directly with minimal framing
            if self.text:
                entity_note = f" (with {self.entity})" if self.entity else ""
                return f"[Witness{entity_note}] {self.text}"
            # Fallback: reconstruct from fields
            entity_text = f" ({self.entity})" if self.entity else ""
            return f"[Witness: {self.moment}{entity_text}] {self.feeling}"

        elif mode == ContextMode.NARRATIVE:
            # If we have text, wrap it in narrative framing
            if self.text:
                return f"(You remember: {self.text})"
            # Fallback: reconstruct from fields
            feeling_phrase = f" You felt {self.feeling}." if self.feeling else ""
            effect_phrase = f" {self.effect}" if self.effect else ""
            entity_phrase = f" ({self.entity})" if self.entity else ""
            return (
                f"(You remember: {self.moment}{entity_phrase}.{feeling_phrase}{effect_phrase})"
            )

        elif mode == ContextMode.WHISPER:
            # Extract essence - if we have text, try to find emotional core
            if self.text:
                # Try to extract a feeling-like phrase from the text
                words = self.text.lower().split()
                # Look for emotion words
                emotion_words = [w for w in words if w in (
                    "felt", "feeling", "honored", "trusted", "seen", "held",
                    "loved", "understood", "connected", "moved", "touched",
                    "grateful", "peaceful", "safe", "warm", "joy", "awe"
                )]
                if emotion_words:
                    return f"(A sense of being {emotion_words[0]} surfaces...)"
                return f"(A witness moment stirs...)"
            # Fallback: use feeling field
            if self.feeling:
                return f"(A sense of {self.feeling} surfaces...)"
            return f"(A moment returns...)"

        elif mode == ContextMode.RITUAL:
            # For ritual mode, use text if available, otherwise structured format
            if self.text:
                entity_line = f"Who: {self.entity}\n" if self.entity else ""
                return (
                    f"(WITNESS MOMENT:\n"
                    f"{entity_line}"
                    f"{self.text})"
                )
            # Fallback: structured format
            entity_line = f"Who: {self.entity}\n" if self.entity else ""
            return (
                f"(WITNESS MOMENT:\n"
                f"What: {self.moment}\n"
                f"{entity_line}"
                f"Feeling: {self.feeling}\n"
                f"Effect: {self.effect})"
            )

        return self.text if self.text else str(self.content)


def create_witness_moment(
    moment: str = "",
    feeling: str = "",
    effect: str = "",
    context: str = "",
    entity: str = "",
    text: str | None = None,
    **kwargs: Any
) -> WitnessMoment:
    """Factory function for creating witness moments.

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. Structured fields remain for search/organization but
    text takes precedence for context composition.

    Args:
        moment: What happened (language naturally indicates direction)
        feeling: The inner response
        effect: What changed or deepened
        context: When/where this happened
        entity: Who was involved (optional)
        text: Primary narrative content (optional). If provided, this is
              the main text that will be used for context composition.
              If not provided, text will be generated from structured fields.
    """
    return WitnessMoment(
        moment=moment,
        feeling=feeling,
        effect=effect,
        context=context,
        entity=entity,
        text=text,
        **kwargs
    )
