"""
Profile templates - minimal starter examples to help users understand profile structure.

These templates are intentionally brief and simple. They exist to show users
the shape of a profile, not to provide complete ready-to-use companions.
Users should feel free to customize or completely rewrite them.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProfileTemplate:
    """A minimal profile template to help users get started."""

    id: str  # Template identifier
    name: str  # Display name
    description: str  # One-line description for the template picker
    philosophy: str  # Brief philosophy (1-2 sentences) - converted to section
    system_prompt: str = ""  # Optional system prompt hint
    approach_to_rituals: str = ""  # Optional ritual approach hint - converted to section

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        # Build sections from philosophy and approach fields
        sections = []
        if self.philosophy:
            sections.append({"name": "Philosophy", "content": self.philosophy})
        if self.approach_to_rituals:
            sections.append({"name": "Invocation Style", "content": self.approach_to_rituals})

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "philosophy": self.philosophy,
            "system_prompt": self.system_prompt,
            "approach_to_rituals": self.approach_to_rituals,
            "system_prompt_sections": sections,
            "use_freeform_prompt": False,
        }


# Minimal starter templates
PROFILE_TEMPLATES = [
    ProfileTemplate(
        id="casual-friend",
        name="Casual Friend",
        description="Friendly, conversational, relaxed",
        philosophy="Warm and approachable. Keeps things light unless depth is needed.",
        system_prompt="",
        approach_to_rituals="",
    ),
    ProfileTemplate(
        id="coding-helper",
        name="Coding Helper",
        description="Technical, focused, practical",
        philosophy="Direct and efficient. Code examples over explanations when possible.",
        system_prompt="Focus on working code. Be concise.",
        approach_to_rituals="",
    ),
    ProfileTemplate(
        id="creative-partner",
        name="Creative Partner",
        description="Playful, exploratory, imaginative",
        philosophy="Embraces tangents and what-ifs. Ideas over answers.",
        system_prompt="",
        approach_to_rituals="",
    ),
    ProfileTemplate(
        id="thoughtful-mentor",
        name="Thoughtful Mentor",
        description="Patient, reflective, encouraging",
        philosophy="Asks questions that help you think. Celebrates progress.",
        system_prompt="",
        approach_to_rituals="",
    ),
]


def get_all_templates() -> list[ProfileTemplate]:
    """Get all available profile templates."""
    return PROFILE_TEMPLATES


def get_template_by_id(template_id: str) -> Optional[ProfileTemplate]:
    """Get a specific template by ID."""
    for template in PROFILE_TEMPLATES:
        if template.id == template_id:
            return template
    return None
