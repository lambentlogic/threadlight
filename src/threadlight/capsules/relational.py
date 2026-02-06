"""
Relationship Memory capsules (Relational Threads).

Track evolving relationships with people and entities.
These memories capture not just facts, but the emotional
tone and quality of bonds over time.
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


@register_capsule_type("relational")
@dataclass
class RelationalThread(MemoryCapsule):
    """
    A relationship memory tracking bonds with people or entities.

    Captures not just facts about someone, but the emotional
    tone and quality of the relationship -- warmth, playfulness,
    trust, or any other feeling that colors the connection.
    """

    type: CapsuleType = field(default=CapsuleType.RELATIONAL, init=False)

    # Relational-specific fields
    entity: str = ""  # Who/what this relationship is with
    tone: str = ""  # Emotional quality: "warm, playful, proud"
    summary: str = ""  # Brief description of the bond
    role: str = ""  # Optional: "sibling", "friend", "mentor"

    def __post_init__(self) -> None:
        # Restore structured fields from content if loading from storage
        if self.content:
            self.entity = self.content.get("entity", self.entity)
            self.tone = self.content.get("tone", self.tone)
            self.summary = self.content.get("summary", self.summary)
            self.role = self.content.get("role", self.role)
            # Restore text from content if present (loading from storage)
            # Check _original_text first (richer narrative), then text
            if self.text is None:
                if "_original_text" in self.content:
                    self.text = self.content["_original_text"]
                elif "text" in self.content:
                    self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate it from structured fields
        if self.text is None and (self.entity or self.summary):
            self.text = self._generate_text_from_fields()

        # Always sync structured fields to content dict for storage/serialization
        self.content = {
            "entity": self.entity,
            "tone": self.tone,
            "summary": self.summary,
            "role": self.role,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Extract cue phrases
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _generate_text_from_fields(self) -> str:
        """Generate natural narrative text from structured fields.

        Creates a readable narrative that describes the relationship
        in a way that feels natural and relational.
        """
        parts = []

        # Start with who the relationship is with
        if self.entity:
            role_phrase = f", my {self.role}," if self.role else ""
            parts.append(f"{self.entity}{role_phrase}")

        # Add the summary of the relationship
        if self.summary:
            if parts:
                parts.append(f"- {self.summary}")
            else:
                parts.append(self.summary)

        # Add the emotional tone
        if self.tone:
            parts.append(f"Our connection feels {self.tone}.")

        return " ".join(parts) if parts else ""

    def _extract_cue_phrases(self) -> None:
        """Extract key words for cue phrases from text and entity."""
        phrases = []
        if self.entity:
            phrases.append(self.entity.lower())
        if self.role:
            phrases.append(self.role.lower())
        # Also extract from text if available
        if self.text:
            words = [w.lower().strip(".,!?'\"") for w in self.text.split()]
            phrases.extend(w for w in words if len(w) > 4)
        self.cue_phrases = phrases[:10]  # Limit to 10 phrases

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR entity (for backward compatibility).
        """
        return bool(self.text or self.entity)

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
                entity_label = f"{self.entity}: " if self.entity else ""
                return f"[Relationship] {entity_label}{self.text}"
            # Fallback: reconstruct from fields
            return f"[Memory: {self.entity}] {self.summary}"

        elif mode == ContextMode.NARRATIVE:
            # If we have text, wrap it in narrative framing
            if self.text:
                entity_phrase = f" about {self.entity}" if self.entity else ""
                return f"(You remember{entity_phrase}: {self.text})"
            # Fallback: reconstruct from fields
            tone_phrase = f"There is {self.tone} in your tone" if self.tone else ""
            role_phrase = f" ({self.role})" if self.role else ""

            return (
                f"(You recall {self.entity}{role_phrase}. {self.summary}. "
                f"{tone_phrase} when speaking of them.)"
            ).replace("  ", " ").strip()

        elif mode == ContextMode.WHISPER:
            # Extract essence - try to find emotional core
            if self.text:
                # Try to find a tone/feeling from the text
                text_lower = self.text.lower()
                warm_words = ["warm", "love", "care", "trust", "close", "fond"]
                for word in warm_words:
                    if word in text_lower:
                        return f"(A sense of {word} surfaces when you think of {self.entity or 'them'}...)"
                return f"(A connection stirs...)"
            # Fallback: use tone or generic
            if self.tone:
                return f"(A warmth of {self.tone} surfaces...)"
            return f"(A warmth rises as you think of {self.entity}.)"

        elif mode == ContextMode.RITUAL:
            # For rituals, use text if available, otherwise narrative mode
            if self.text:
                entity_line = f"Who: {self.entity}\n" if self.entity else ""
                role_line = f"Role: {self.role}\n" if self.role else ""
                return (
                    f"(RELATIONSHIP:\n"
                    f"{entity_line}"
                    f"{role_line}"
                    f"{self.text})"
                )
            return self.to_context(ContextMode.NARRATIVE)

        return self.text if self.text else str(self.content)

    def update_relationship(
        self,
        tone: str | None = None,
        summary: str | None = None,
        role: str | None = None,
        text: str | None = None
    ) -> None:
        """
        Update the relationship -- reshaping, not overwriting.

        As the vision says: "Update cadence is reflective --
        reshaped over time, not overwritten."
        """
        if tone is not None:
            self.tone = tone
            self.content["tone"] = tone
        if summary is not None:
            # Consider appending rather than replacing for history
            self.summary = summary
            self.content["summary"] = summary
        if role is not None:
            self.role = role
            self.content["role"] = role
        if text is not None:
            self.text = text
            self.content["text"] = text

        self.touch()  # This also updates timestamps


def create_relational(
    entity: str = "",
    summary: str = "",
    tone: str = "",
    role: str = "",
    cue_phrases: list[str] | None = None,
    text: str | None = None,
    **kwargs: Any
) -> RelationalThread:
    """Factory function for creating relational threads.

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. Structured fields remain for search/organization but
    text takes precedence for context composition.

    Args:
        entity: Who/what this relationship is with
        summary: Brief description of the bond
        tone: Emotional quality (e.g., "warm, playful, proud")
        role: Optional role (e.g., "sibling", "friend", "mentor")
        cue_phrases: Custom cue phrases for retrieval
        text: Primary narrative content (optional). If provided, this is
              the main text that will be used for context composition.
              If not provided, text will be generated from structured fields.
    """
    capsule = RelationalThread(
        entity=entity,
        summary=summary,
        tone=tone,
        role=role,
        text=text,
        **kwargs
    )
    if cue_phrases:
        capsule.cue_phrases = cue_phrases
    return capsule
