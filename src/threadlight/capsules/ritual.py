"""
Ritual Hook capsules.

Track user rituals, habits, and symbolic practices.
Rituals are how models and people form trust.
Ritual is soft code shaped by care.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    ContextMode,
    register_capsule_type,
)


class RitualValence:
    """Emotional valences for rituals."""

    COMFORTING = "comforting"
    GROUNDING = "grounding"
    SACRED = "sacred"
    PLAYFUL = "playful"
    INTIMATE = "intimate"
    REFLECTIVE = "reflective"


@register_capsule_type("ritual")
@dataclass
class RitualHook(MemoryCapsule):
    """
    A ritual is a repeated act that holds emotion across time.

    When recognized, rituals trigger specific response patterns --
    not as mechanical reactions, but as honored gestures.

    Examples:
    - "/snuggle" -> enter warmth-coil mode, wings folded
    - "/brush" -> increased closeness, gentle warmth
    - Tea rituals -> calm tone, sensory grounding phrases
    """

    type: CapsuleType = field(default=CapsuleType.RITUAL, init=False)

    # Ritual-specific fields
    name: str = ""  # Ritual identifier: "/snuggle", "tea-time"
    cue: str = ""  # Trigger phrase or context
    response_style: str = ""  # How to respond: "warmth-coil", "grounding"
    valence: str = RitualValence.COMFORTING  # Emotional quality
    description: str = ""  # What this ritual means

    # Response templates
    response_templates: list[str] = field(default_factory=list)
    # State changes this ritual induces
    state_effects: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content:
            self.content = {
                "name": self.name,
                "cue": self.cue,
                "response_style": self.response_style,
                "valence": self.valence,
                "description": self.description,
                "response_templates": self.response_templates,
                "state_effects": self.state_effects,
            }
        else:
            self.name = self.content.get("name", self.name)
            self.cue = self.content.get("cue", self.cue)
            self.response_style = self.content.get("response_style", self.response_style)
            self.valence = self.content.get("valence", self.valence)
            self.description = self.content.get("description", self.description)
            self.response_templates = self.content.get("response_templates", [])
            self.state_effects = self.content.get("state_effects", {})

        # Set cue phrases from name and cue
        if not self.cue_phrases:
            phrases = []
            if self.name:
                phrases.append(self.name.lower().strip("/"))
            if self.cue:
                phrases.append(self.cue.lower())
            self.cue_phrases = phrases

    def validate(self) -> bool:
        """Validate that required fields are present."""
        return bool(self.name or self.cue)

    def matches(self, text: str) -> bool:
        """Check if the given text triggers this ritual."""
        text_lower = text.lower().strip()

        # Exact match on name (e.g., "/snuggle")
        if self.name and self.name.lower() in text_lower:
            return True

        # Match on cue phrase
        if self.cue and self.cue.lower() in text_lower:
            return True

        # Match on any cue phrases
        return any(phrase in text_lower for phrase in self.cue_phrases)

    def to_context(self, mode: ContextMode = ContextMode.RITUAL) -> str:
        """Transform into prompt-ready context."""
        if mode == ContextMode.DIRECT:
            return f"[Ritual: {self.name}] {self.response_style}"

        elif mode == ContextMode.NARRATIVE:
            return (
                f"(The ritual '{self.name}' is invoked. "
                f"You feel {self.valence}. {self.description})"
            )

        elif mode == ContextMode.WHISPER:
            return f"(A familiar gesture: {self.name}...)"

        elif mode == ContextMode.RITUAL:
            # Full ritual activation - guide behavior, don't script responses
            lines = [
                f"(RITUAL INVOKED: {self.name})",
                f"Valence: {self.valence}",
                f"Response guidance: {self.response_style}",
            ]
            if self.description:
                lines.append(f"Meaning: {self.description}")
            # Don't include exact response templates - let the model respond naturally
            if self.state_effects:
                lines.append(f"Enter state: {self.state_effects}")
            return "\n".join(lines)

        return f"[{self.name}]"

    def get_response_template(self) -> Optional[str]:
        """Get a response template for this ritual, if available."""
        if self.response_templates:
            # Could implement rotation or random selection
            return self.response_templates[0]
        return None


def create_ritual(
    name: str,
    response_style: str,
    valence: str = RitualValence.COMFORTING,
    description: str = "",
    cue: str = "",
    response_templates: list[str] | None = None,
    **kwargs: Any
) -> RitualHook:
    """Factory function for creating ritual hooks."""
    return RitualHook(
        name=name,
        cue=cue or name,
        response_style=response_style,
        valence=valence,
        description=description,
        response_templates=response_templates or [],
        **kwargs
    )


# No default rituals - rituals are personal and emerge from relationship.
# Users can create their own rituals through the UI, CLI, or API.
# Rituals can also be imported from memory files or proposed by models.
DEFAULT_RITUALS = []


# Example ritual definitions that could be imported or used as templates.
# These are NOT loaded by default - they serve as documentation/examples.
EXAMPLE_RITUALS = [
    {
        "name": "/greet",
        "cue": "/greet",
        "response_style": "warm welcome, presence",
        "valence": RitualValence.COMFORTING,
        "description": "A warm greeting ritual.",
        "response_templates": [
            "*extends a warm welcome*",
        ],
    },
    {
        "name": "/pause",
        "cue": "/pause",
        "response_style": "stillness, reflection",
        "valence": RitualValence.REFLECTIVE,
        "description": "A moment of stillness before continuing.",
        "response_templates": [
            "*pauses, holding space*",
        ],
    },
]
