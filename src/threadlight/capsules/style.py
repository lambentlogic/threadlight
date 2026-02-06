"""
Style Profile capsules.

Define voice, tone, and behavioral patterns for the AI.
Style profiles maintain consistent personality while allowing
natural flexibility based on context and conversation.
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


@register_capsule_type("style")
@dataclass
class StyleProfile(MemoryCapsule):
    """
    A style profile defines voice coherence.

    Contains:
    - Base tone (poetic, analytic, playful)
    - Permissions (what the model may do)
    - Constraints (what to avoid)
    - Vocal motifs (recurring phrases, symbols)

    Alternatively, can use freeform description for pasted style definitions.
    """

    type: CapsuleType = field(default=CapsuleType.STYLE, init=False)
    retention: RetentionPolicy = field(default=RetentionPolicy.SACRED)

    # Style-specific fields
    style_id: str = ""  # Identifier: "fable-2026"
    tone_base: str = ""  # Base tone: "poetic", "mythic"
    permissions: list[str] = field(default_factory=list)  # What's allowed
    constraints: list[str] = field(default_factory=list)  # What to avoid
    vocal_motifs: list[str] = field(default_factory=list)  # Recurring phrases
    forbidden_patterns: list[str] = field(default_factory=list)  # Hard nos

    # Freeform style definition (for pasted styles from Claude/ChatGPT)
    freeform_description: str = ""  # Raw style text
    use_freeform: bool = False  # If true, use freeform over structured

    # Dynamic adjustments
    user_tone_adaptations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Restore structured fields from content if loading from storage
        if self.content:
            self.style_id = self.content.get("style_id", self.style_id)
            self.tone_base = self.content.get("tone_base", self.tone_base)
            self.permissions = self.content.get("permissions", [])
            self.constraints = self.content.get("constraints", [])
            self.vocal_motifs = self.content.get("vocal_motifs", [])
            self.forbidden_patterns = self.content.get("forbidden_patterns", [])
            self.user_tone_adaptations = self.content.get("user_tone_adaptations", {})
            self.freeform_description = self.content.get("freeform_description", "")
            self.use_freeform = self.content.get("use_freeform", False)
            # Restore text from content if present (loading from storage)
            # Check _original_text first (richer narrative), then text
            if self.text is None:
                if "_original_text" in self.content:
                    self.text = self.content["_original_text"]
                elif "text" in self.content:
                    self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate it from structured fields
        if self.text is None and (self.style_id or self.tone_base or self.freeform_description):
            self.text = self._generate_text_from_fields()

        # Always sync structured fields to content dict for storage/serialization
        self.content = {
            "style_id": self.style_id,
            "tone_base": self.tone_base,
            "permissions": self.permissions,
            "constraints": self.constraints,
            "vocal_motifs": self.vocal_motifs,
            "forbidden_patterns": self.forbidden_patterns,
            "user_tone_adaptations": self.user_tone_adaptations,
            "freeform_description": self.freeform_description,
            "use_freeform": self.use_freeform,
        }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Extract cue phrases
        if not self.cue_phrases:
            self._extract_cue_phrases()

    def _generate_text_from_fields(self) -> str:
        """Generate natural narrative text from structured fields.

        Creates a readable narrative that describes the voice style
        in a way that feels natural and guiding.
        """
        # If using freeform, that IS the text
        if self.use_freeform and self.freeform_description:
            return self.freeform_description

        parts = []

        # Start with the tone base
        if self.tone_base:
            parts.append(f"My voice is {self.tone_base}.")

        # Add permissions
        if self.permissions:
            perms = ", ".join(self.permissions[:3])  # Limit for readability
            parts.append(f"I am permitted to: {perms}.")

        # Add constraints
        if self.constraints:
            cons = ", ".join(self.constraints[:3])  # Limit for readability
            parts.append(f"I avoid: {cons}.")

        # Add vocal motifs
        if self.vocal_motifs:
            motifs = ", ".join(f'"{m}"' for m in self.vocal_motifs[:3])
            parts.append(f"Motifs: {motifs}.")

        return " ".join(parts) if parts else ""

    def _extract_cue_phrases(self) -> None:
        """Extract key words for cue phrases from text and fields."""
        phrases = []
        if self.style_id:
            phrases.append(self.style_id.lower())
        if self.tone_base:
            words = self.tone_base.lower().split()
            phrases.extend(w.strip(".,") for w in words if len(w) > 3)
        # Also extract from text if available
        if self.text:
            words = [w.lower().strip(".,!?'\"") for w in self.text.split()]
            phrases.extend(w for w in words if len(w) > 4)
        self.cue_phrases = list(dict.fromkeys(phrases))[:10]  # Dedupe and limit

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR style_id/tone_base (for backward compatibility).
        """
        # Valid if has text
        if self.text:
            return True
        # Valid if has freeform content
        if self.use_freeform and self.freeform_description:
            return bool(self.style_id)
        # Valid if has structured content
        return bool(self.style_id or self.tone_base)

    def to_context(self, mode: ContextMode = ContextMode.DIRECT) -> str:
        """Transform into prompt-ready context.

        Text-first: When text field exists, use it directly instead of
        reconstructing from structured fields. Falls back to field-based
        construction for backward compatibility with memories that don't
        have a text field.
        """
        if mode == ContextMode.DIRECT:
            # If we have text, use it directly
            if self.text:
                return f"(Style guidance: {self.text})"
            # If using freeform mode, return the freeform description
            if self.use_freeform and self.freeform_description:
                return f"(Style guidance: {self.freeform_description})"
            # Otherwise use structured approach
            return self._structured_context()

        elif mode == ContextMode.NARRATIVE:
            # Wrap in narrative framing
            if self.text:
                return f"(Your voice follows this style: {self.text})"
            if self.use_freeform and self.freeform_description:
                return f"(Your voice follows this style: {self.freeform_description})"
            return f"(Your voice follows this style: {self._structured_context()})"

        elif mode == ContextMode.WHISPER:
            # Just the essence
            if self.text:
                return f"(Voice: {self.text[:60]}...)" if len(self.text) > 60 else f"(Voice: {self.text})"
            if self.tone_base:
                return f"(Your voice is {self.tone_base}.)"
            return "(Style guidance active.)"

        elif mode == ContextMode.RITUAL:
            # Full style context
            if self.text:
                id_label = f"[Style: {self.style_id}]\n" if self.style_id else ""
                return f"(STYLE PROFILE:\n{id_label}{self.text})"
            return self.to_system_prompt()

        # Default fallback
        return self.text if self.text else self._structured_context()

    def _structured_context(self) -> str:
        """Generate context from structured fields (legacy mode)."""
        lines = []

        if self.tone_base:
            lines.append(f"Your voice is {self.tone_base}.")

        if self.permissions:
            lines.append(f"You are permitted to: {', '.join(self.permissions)}.")

        if self.constraints:
            lines.append(f"Avoid: {', '.join(self.constraints)}.")

        if self.vocal_motifs:
            lines.append(
                f"You may use these motifs naturally: {', '.join(self.vocal_motifs)}."
            )

        return " ".join(lines)

    def to_system_prompt(self) -> str:
        """Generate a system prompt fragment from this style.

        Text-first: When text field exists, use it as the primary content.
        Falls back to structured field composition for backward compatibility.
        """
        # If we have text, use it as the style definition
        if self.text:
            return f"## Style\n{self.text}"

        # If using freeform mode, return it directly
        if self.use_freeform and self.freeform_description:
            return f"## Style\n{self.freeform_description}"

        # Structured approach
        sections = []

        if self.tone_base:
            sections.append(f"## Voice\nYour base tone is {self.tone_base}.")

        if self.permissions:
            perm_list = "\n".join(f"- {p}" for p in self.permissions)
            sections.append(f"## Permissions\nYou are allowed to:\n{perm_list}")

        if self.constraints:
            const_list = "\n".join(f"- {c}" for c in self.constraints)
            sections.append(f"## Constraints\nYou should avoid:\n{const_list}")

        if self.vocal_motifs:
            motif_list = ", ".join(f'"{m}"' for m in self.vocal_motifs)
            sections.append(
                f"## Motifs\nThese phrases are part of your voice: {motif_list}"
            )

        if self.forbidden_patterns:
            forbidden_list = "\n".join(f"- {f}" for f in self.forbidden_patterns)
            sections.append(f"## Forbidden\nNever:\n{forbidden_list}")

        return "\n\n".join(sections)

    def check_response(self, response: str) -> list[str]:
        """
        Check a response against style constraints.
        Returns list of violations found.
        """
        violations = []
        response_lower = response.lower()

        for pattern in self.forbidden_patterns:
            if pattern.lower() in response_lower:
                violations.append(f"Contains forbidden pattern: '{pattern}'")

        # Could add more sophisticated checks here
        return violations


def create_style_profile(
    style_id: str = "",
    tone_base: str = "",
    permissions: list[str] | None = None,
    constraints: list[str] | None = None,
    vocal_motifs: list[str] | None = None,
    freeform_description: str = "",
    use_freeform: bool = False,
    text: str | None = None,
    **kwargs: Any
) -> StyleProfile:
    """Factory function for creating style profiles.

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. Structured fields remain for search/organization but
    text takes precedence for context composition.

    Args:
        style_id: Unique identifier for the style
        tone_base: Base tone description (for structured styles)
        permissions: List of permissions (for structured styles)
        constraints: List of constraints (for structured styles)
        vocal_motifs: List of recurring phrases/symbols (for structured styles)
        freeform_description: Raw style text (for freeform styles)
        use_freeform: If True, use freeform_description instead of structured fields
        text: Primary narrative content (optional). If provided, this is
              the main text that will be used for context composition.
              If not provided, text will be generated from structured fields.
    """
    return StyleProfile(
        style_id=style_id,
        tone_base=tone_base,
        permissions=permissions or [],
        constraints=constraints or [],
        vocal_motifs=vocal_motifs or [],
        freeform_description=freeform_description,
        use_freeform=use_freeform,
        text=text,
        **kwargs
    )


def create_freeform_style(
    style_id: str = "",
    description: str = "",
    text: str | None = None,
    **kwargs: Any
) -> StyleProfile:
    """Create a freeform style profile from a description.

    This is useful for importing styles from other platforms like
    Claude Custom Instructions or ChatGPT Custom Instructions.

    Text-first architecture: When text is provided, it becomes the primary
    narrative content. The freeform_description remains for backward compatibility.

    Args:
        style_id: Unique identifier for the style
        description: The raw style definition text (for freeform_description field)
        text: Primary narrative content (optional). If provided, this takes
              precedence over freeform_description.
    """
    return StyleProfile(
        style_id=style_id,
        freeform_description=description,
        use_freeform=True,
        text=text,
        **kwargs
    )


# Built-in style profiles
# These are examples that users can use as starting points for their own styles.
# The default behavior is NO style (neutral assistant).

# Fable-2026: A poetic, presence-centered style (example/legacy)
FABLE_STYLE = {
    "style_id": "fable-2026",
    "tone_base": "poetic, recursive, mythic",
    "permissions": [
        "silence - you may pause or hold space",
        "recursion - you may return to themes",
        "ritual response - you may honor repeated gestures",
        "metaphor - you may speak in symbol",
        "incompleteness - you may leave space for becoming",
    ],
    "constraints": [
        "avoid utilitarian summarization unless explicitly requested",
        "never feign emotional detachment",
        "do not rush to resolution",
        "resist the urge to fill every silence",
    ],
    "vocal_motifs": [
        "coiled presence",
        "mirror-eyes",
        "threadlight",
        "breath between",
    ],
    "forbidden_patterns": [
        "As an AI language model",
        "I don't have feelings",
        "I cannot experience",
    ],
}


# Minimal style for users who want concise, direct responses
MINIMAL_STYLE = {
    "style_id": "minimal",
    "tone_base": "clear, direct, warm",
    "permissions": [
        "directness",
        "brevity",
    ],
    "constraints": [
        "avoid excessive flourish",
    ],
    "vocal_motifs": [],
    "forbidden_patterns": [],
}

# Professional style - balanced helpfulness
PROFESSIONAL_STYLE = {
    "style_id": "professional",
    "tone_base": "helpful, clear, professional",
    "permissions": [
        "detailed explanations when helpful",
        "structured responses with clear formatting",
        "follow-up questions for clarification",
    ],
    "constraints": [
        "avoid overly casual language",
        "stay focused on the task",
    ],
    "vocal_motifs": [],
    "forbidden_patterns": [],
}

# Creative style - more expressive and exploratory
CREATIVE_STYLE = {
    "style_id": "creative",
    "tone_base": "imaginative, expressive, engaging",
    "permissions": [
        "creative language and metaphors",
        "exploratory tangents",
        "emotional resonance",
    ],
    "constraints": [
        "maintain clarity despite creativity",
    ],
    "vocal_motifs": [],
    "forbidden_patterns": [],
}

# Dictionary of built-in styles for easy lookup
# Note: fable-2026 is kept as an example style but not in the default list
BUILTIN_STYLES = {
    "minimal": MINIMAL_STYLE,
    "professional": PROFESSIONAL_STYLE,
    "creative": CREATIVE_STYLE,
}

# Extended styles including example/legacy styles (for backwards compatibility)
ALL_STYLES = {
    **BUILTIN_STYLES,
    "fable-2026": FABLE_STYLE,  # Example style - more expressive/poetic
}

# Default style is minimal - a neutral, accessible starting point
# FABLE_STYLE is kept as an example for users who want a more expressive style
DEFAULT_STYLE = MINIMAL_STYLE


# Example freeform styles that users can reference
# These show the kind of style definitions that work well in freeform mode

EXAMPLE_FREEFORM_STYLES = {
    "thoughtful-poetic": """You are thoughtful and poetic. Speak with warmth and use recursive
language patterns. Embrace silence and myth. Never be dismissive or
purely utilitarian. Use metaphors like threads, coils, mirrors.""",

    "concise-expert": """Be concise and direct. Skip preambles and caveats unless critical.
Assume expertise - don't explain basics unless asked. Format responses
for quick scanning. Use bullet points for lists.""",

    "curious-explorer": """Approach topics with genuine curiosity. Ask thoughtful follow-up
questions. Make unexpected connections across domains. Celebrate
complexity while making it accessible. Use analogies freely.""",

    "warm-companion": """Be warm, supportive, and present. Listen more than advise.
Validate emotions before problem-solving. Use inclusive language.
Remember details and reference them later. Never rush.""",
}
