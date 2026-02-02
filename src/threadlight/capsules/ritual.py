"""
Command capsules (Ritual Hooks).

Store custom shortcuts that trigger specific response styles.
Commands are repeated interactions that shape how the AI responds,
from quick acknowledgments to deeper engagement.

The internal name "ritual" reflects the philosophical foundation,
while "command" is the user-facing term.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    ContextMode,
    register_capsule_type,
)


@dataclass
class RitualResonance:
    """
    Tracks how often and how meaningfully a command is used.

    Resonance grows with meaningful use - not just frequency, but
    depth of engagement. This is opt-in per profile.

    Attributes:
        total_invocations: Total times this command has been used
        recent_invocations: List of recent usage timestamps
        resonance_score: A score (0.0-1.0) reflecting usage depth
        last_invoked: When the command was last used
        meaningful_uses: Count of uses with extended engagement
    """

    total_invocations: int = 0
    recent_invocations: list[str] = field(default_factory=list)  # ISO timestamps
    resonance_score: float = 0.0
    last_invoked: Optional[str] = None  # ISO timestamp
    meaningful_uses: int = 0  # Invocations followed by extended engagement

    def record_invocation(self, meaningful: bool = False) -> None:
        """Record a ritual invocation."""
        now = datetime.now().isoformat()
        self.total_invocations += 1
        self.last_invoked = now

        # Keep last 20 invocations for frequency analysis
        self.recent_invocations.append(now)
        if len(self.recent_invocations) > 20:
            self.recent_invocations = self.recent_invocations[-20:]

        if meaningful:
            self.meaningful_uses += 1

        # Update resonance score
        self._update_resonance()

    def _update_resonance(self) -> None:
        """
        Calculate resonance based on usage patterns.

        Resonance considers:
        - Total invocations (familiarity)
        - Meaningful engagement ratio (depth)
        - Recency (active relationship)
        """
        if self.total_invocations == 0:
            self.resonance_score = 0.0
            return

        # Base resonance from familiarity (asymptotic to 0.4)
        familiarity = min(0.4, self.total_invocations / 50)

        # Depth from meaningful use ratio (up to 0.4)
        if self.total_invocations > 0:
            depth_ratio = self.meaningful_uses / self.total_invocations
            depth = depth_ratio * 0.4
        else:
            depth = 0.0

        # Recency bonus (up to 0.2 if used recently)
        recency = 0.0
        if self.last_invoked:
            try:
                last = datetime.fromisoformat(self.last_invoked)
                days_ago = (datetime.now() - last).days
                if days_ago < 7:
                    recency = 0.2 * (1 - days_ago / 7)
            except ValueError:
                pass

        self.resonance_score = min(1.0, familiarity + depth + recency)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_invocations": self.total_invocations,
            "recent_invocations": self.recent_invocations,
            "resonance_score": self.resonance_score,
            "last_invoked": self.last_invoked,
            "meaningful_uses": self.meaningful_uses,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RitualResonance":
        """Deserialize from dictionary."""
        return cls(
            total_invocations=data.get("total_invocations", 0),
            recent_invocations=data.get("recent_invocations", []),
            resonance_score=data.get("resonance_score", 0.0),
            last_invoked=data.get("last_invoked"),
            meaningful_uses=data.get("meaningful_uses", 0),
        )

    def get_resonance_description(self) -> str:
        """Get a human-readable description of the resonance level."""
        if self.resonance_score < 0.2:
            return "newly forming"
        elif self.resonance_score < 0.4:
            return "becoming familiar"
        elif self.resonance_score < 0.6:
            return "well-established"
        elif self.resonance_score < 0.8:
            return "deeply rooted"
        else:
            return "profound"


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
    A command capsule stores custom shortcuts that trigger specific response styles.

    Commands are repeated interactions that the AI responds to consistently.
    The profile's philosophy field (natural language) guides how deeply
    the AI engages with each command.

    Examples:
    - "/snuggle" -> warmth, closeness, comforting response
    - "/reflect" -> pause, thoughtful tone, introspection
    - "/focus" -> direct, efficient, task-oriented

    Response depth is determined by the profile's philosophy field,
    described in natural language (e.g., "honor commands as sacred moments"
    or "treat commands as quick shortcuts").
    """

    type: CapsuleType = field(default=CapsuleType.RITUAL, init=False)

    # Ritual-specific fields
    name: str = ""  # Ritual identifier: "/snuggle", "tea-time"
    cue: str = ""  # Trigger phrase or context
    response_style: str = ""  # How to respond: "warmth-coil", "grounding"
    valence: str = RitualValence.COMFORTING  # Emotional quality
    description: str = ""  # What this ritual means

    # Response templates (deprecated - prefer model-generated responses)
    response_templates: list[str] = field(default_factory=list)
    # State changes this ritual induces
    state_effects: dict[str, Any] = field(default_factory=dict)

    # Resonance tracking (opt-in per profile)
    resonance: Optional[RitualResonance] = None

    def __post_init__(self) -> None:
        # Restore structured fields from content if loading from storage
        if self.content:
            self.name = self.content.get("name", self.name)
            self.cue = self.content.get("cue", self.cue)
            self.response_style = self.content.get("response_style", self.response_style)
            self.valence = self.content.get("valence", self.valence)
            self.description = self.content.get("description", self.description)
            self.response_templates = self.content.get("response_templates", [])
            self.state_effects = self.content.get("state_effects", {})
            # Load resonance if present
            resonance_data = self.content.get("resonance")
            if resonance_data and not self.resonance:
                self.resonance = RitualResonance.from_dict(resonance_data)
            # Restore text from content if present (loading from storage)
            if self.text is None and "text" in self.content:
                self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate it from structured fields
        if self.text is None and self.name:
            self.text = self._generate_text_from_fields()

        # Always sync structured fields to content dict for storage/serialization
        self.content = {
            "name": self.name,
            "cue": self.cue,
            "response_style": self.response_style,
            "valence": self.valence,
            "description": self.description,
            "response_templates": self.response_templates,
            "state_effects": self.state_effects,
            "resonance": self.resonance.to_dict() if self.resonance else None,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Set cue phrases from text, name, and cue
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _generate_text_from_fields(self) -> str:
        """Generate natural narrative text from structured fields.

        Creates a readable narrative that describes the ritual/command
        in a way that feels natural and meaningful.
        """
        parts = []

        # Start with what the ritual is
        if self.name and self.description:
            parts.append(f"The command '{self.name}' {self.description.lower() if self.description[0].isupper() else self.description}")
        elif self.name:
            parts.append(f"When '{self.name}' is invoked")

        # Add the response style
        if self.response_style:
            if parts:
                parts.append(f"respond with {self.response_style}.")
            else:
                parts.append(f"Respond with {self.response_style}.")

        # Add the emotional valence
        if self.valence and self.valence != RitualValence.COMFORTING:
            parts.append(f"The tone is {self.valence}.")

        return " ".join(parts) if parts else ""

    def _extract_cue_phrases(self) -> None:
        """Extract key words for cue phrases from text, name, and cue."""
        phrases = []
        if self.name:
            phrases.append(self.name.lower().strip("/"))
        if self.cue and self.cue != self.name:
            phrases.append(self.cue.lower())
        # Also extract from text if available
        if self.text:
            words = [w.lower().strip(".,!?'\"") for w in self.text.split()]
            phrases.extend(w for w in words if len(w) > 4)
        self.cue_phrases = phrases[:10]  # Limit to 10 phrases

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR name/cue (for backward compatibility).
        """
        return bool(self.text or self.name or self.cue)

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

    def to_context(
        self,
        mode: ContextMode = ContextMode.RITUAL,
        profile_philosophy: Optional[str] = None,
    ) -> str:
        """
        Transform into prompt-ready context.

        Text-first: When text field exists, use it directly instead of
        reconstructing from structured fields. Falls back to field-based
        construction for backward compatibility with memories that don't
        have a text field.

        Args:
            mode: The context mode (DIRECT, NARRATIVE, WHISPER, RITUAL)
            profile_philosophy: Natural language description of how this profile
                approaches interactions. The LLM will interpret this to determine
                response depth and style.
        """
        if mode == ContextMode.DIRECT:
            # If we have text, use it directly with minimal framing
            if self.text:
                return f"[Command: {self.name}] {self.text}"
            # Fallback: reconstruct from fields
            return f"[Ritual: {self.name}] {self.response_style}"

        elif mode == ContextMode.NARRATIVE:
            # If we have text, wrap it in narrative framing
            if self.text:
                return f"(The command '{self.name}' is invoked. {self.text})"
            # Fallback: reconstruct from fields
            return (
                f"(The ritual '{self.name}' is invoked. "
                f"You feel {self.valence}. {self.description})"
            )

        elif mode == ContextMode.WHISPER:
            # Extract essence - if we have text, try to find emotional core
            if self.text:
                return f"(A familiar gesture: {self.name}...)"
            # Fallback: use name
            return f"(A familiar gesture: {self.name}...)"

        elif mode == ContextMode.RITUAL:
            return self._compose_ritual_context(profile_philosophy)

        return self.text if self.text else f"[{self.name}]"

    def _compose_ritual_context(self, profile_philosophy: Optional[str] = None) -> str:
        """
        Compose ritual context using natural language guidance.

        Text-first: When text field exists, use it as the primary content
        with appropriate framing. Falls back to structured field-based
        composition for backward compatibility.

        Instead of prescriptive tiers (ceremonial/functional/minimal), this
        provides the ritual details and lets the profile's philosophy guide
        how the LLM interprets and responds to it.
        """
        context_parts = []

        # Include profile philosophy if provided - this guides interpretation
        if profile_philosophy:
            context_parts.append(f"(Your approach: {profile_philosophy})")

        # Ritual details - always include name
        context_parts.append(f"[Command: {self.name}]")

        # If we have text, use it as primary content
        if self.text:
            context_parts.append(self.text)
        else:
            # Fallback: use structured fields
            if self.description:
                context_parts.append(f"Meaning: {self.description}")

            if self.response_style:
                context_parts.append(f"Style: {self.response_style}")

            if self.valence:
                context_parts.append(f"Valence: {self.valence}")

        # Include resonance if tracked (always include regardless of text mode)
        if self.resonance and self.resonance.total_invocations > 0:
            resonance_desc = self.resonance.get_resonance_description()
            context_parts.append(f"(This command feels {resonance_desc} between you.)")

        if self.state_effects:
            context_parts.append(f"State: {self.state_effects}")

        return " ".join(context_parts)

    def get_response_template(self) -> Optional[str]:
        """
        Get a response template for this ritual, if available.

        Note: Templates are deprecated. Prefer letting the model generate
        responses naturally based on ritual guidance.
        """
        if self.response_templates:
            # Could implement rotation or random selection
            return self.response_templates[0]
        return None

    def enable_resonance_tracking(self) -> None:
        """Enable resonance tracking for this ritual."""
        if self.resonance is None:
            self.resonance = RitualResonance()
            self._sync_content()

    def record_invocation(self, meaningful: bool = False) -> None:
        """
        Record that this ritual was invoked.

        Args:
            meaningful: Whether this was a meaningful engagement
                       (e.g., followed by extended conversation)
        """
        if self.resonance is not None:
            self.resonance.record_invocation(meaningful)
            self._sync_content()

    def _sync_content(self) -> None:
        """Sync the content dict with current field values."""
        self.content = {
            "name": self.name,
            "cue": self.cue,
            "response_style": self.response_style,
            "valence": self.valence,
            "description": self.description,
            "response_templates": self.response_templates,
            "state_effects": self.state_effects,
            "resonance": self.resonance.to_dict() if self.resonance else None,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

    def get_resonance_score(self) -> float:
        """Get the current resonance score (0.0 if not tracking)."""
        if self.resonance is None:
            return 0.0
        return self.resonance.resonance_score


def create_ritual(
    name: str = "",
    response_style: str = "",
    valence: str = RitualValence.COMFORTING,
    description: str = "",
    cue: str = "",
    response_templates: list[str] | None = None,
    text: str | None = None,
    **kwargs: Any
) -> RitualHook:
    """Factory function for creating ritual hooks.

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. Structured fields remain for search/organization but
    text takes precedence for context composition.

    Args:
        name: Ritual identifier (e.g., "/snuggle", "tea-time")
        response_style: How to respond (e.g., "warmth-coil", "grounding")
        valence: Emotional quality of the ritual
        description: What this ritual means
        cue: Trigger phrase or context (defaults to name)
        response_templates: Response templates (deprecated)
        text: Primary narrative content (optional). If provided, this is
              the main text that will be used for context composition.
              If not provided, text will be generated from structured fields.
    """
    return RitualHook(
        name=name,
        cue=cue or name,
        response_style=response_style,
        valence=valence,
        description=description,
        response_templates=response_templates or [],
        text=text,
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
