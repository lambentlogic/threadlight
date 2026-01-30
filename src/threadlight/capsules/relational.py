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
        # Sync content dict with explicit fields
        if not self.content:
            self.content = {
                "entity": self.entity,
                "tone": self.tone,
                "summary": self.summary,
                "role": self.role,
            }
        else:
            # If content provided, extract to fields
            self.entity = self.content.get("entity", self.entity)
            self.tone = self.content.get("tone", self.tone)
            self.summary = self.content.get("summary", self.summary)
            self.role = self.content.get("role", self.role)

        # Auto-generate cue phrases if not provided
        if not self.cue_phrases and self.entity:
            self.cue_phrases = [self.entity.lower()]

    def validate(self) -> bool:
        """Validate that required fields are present."""
        return bool(self.entity and self.summary)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context."""
        if mode == ContextMode.DIRECT:
            return f"[Memory: {self.entity}] {self.summary}"

        elif mode == ContextMode.NARRATIVE:
            tone_phrase = f"There is {self.tone} in your tone" if self.tone else ""
            role_phrase = f" ({self.role})" if self.role else ""

            return (
                f"(You recall {self.entity}{role_phrase}. {self.summary}. "
                f"{tone_phrase} when speaking of them.)"
            ).replace("  ", " ").strip()

        elif mode == ContextMode.WHISPER:
            # Subtle hint without explicit mention
            return f"(A warmth rises as you think of {self.entity}.)"

        elif mode == ContextMode.RITUAL:
            # For rituals, relational context is supportive
            return self.to_context(ContextMode.NARRATIVE)

        return str(self.content)

    def update_relationship(
        self,
        tone: str | None = None,
        summary: str | None = None,
        role: str | None = None
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

        self.touch()  # This also updates timestamps


def create_relational(
    entity: str,
    summary: str,
    tone: str = "",
    role: str = "",
    cue_phrases: list[str] | None = None,
    **kwargs: Any
) -> RelationalThread:
    """Factory function for creating relational threads."""
    capsule = RelationalThread(
        entity=entity,
        summary=summary,
        tone=tone,
        role=role,
        **kwargs
    )
    if cue_phrases:
        capsule.cue_phrases = cue_phrases
    return capsule
