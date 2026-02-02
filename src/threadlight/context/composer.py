"""
Context composer for Threadlight.

Transforms memory capsules into prompt-ready context that
preserves emotional resonance and relational meaning.

Composition modes shape how memories surface:
- DIRECT: Factual integration ("You know that...")
- NARRATIVE: Story-like framing ("You recall...")
- WHISPER: Subtle tone cues ("There is warmth when...")
- RITUAL: Full activation for command invocations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from threadlight.capsules.base import MemoryCapsule, ContextMode, CapsuleType
from threadlight.capsules.style import StyleProfile


class CompositionStrategy(str, Enum):
    """How to arrange multiple capsules in context."""

    SEQUENTIAL = "sequential"  # One after another
    LAYERED = "layered"        # Important first, whispers last
    INTERWOVEN = "interwoven"  # Mixed by type for natural flow


class SoftMemoryMode(str, Enum):
    """How to include soft memory (conversation history) in context."""

    DISABLED = "disabled"      # Don't include soft memory
    RELEVANT = "relevant"      # Include relevant past messages
    RECENT = "recent"          # Include recent messages from any conversation


@dataclass
class ComposedContext:
    """The result of context composition."""

    # System prompt components
    identity_prompt: str = ""
    style_prompt: str = ""
    memory_context: str = ""
    soft_memory_context: str = ""  # Past conversation history

    # The full composed system message
    system_message: str = ""

    # Metadata
    capsules_used: list[str] = field(default_factory=list)
    capsule_modes: dict[str, str] = field(default_factory=dict)  # id -> mode used
    active_rituals: list[str] = field(default_factory=list)
    soft_memory_messages: int = 0  # Number of past messages included
    token_estimate: int = 0
    truncated: bool = False  # True if context was truncated due to token limit

    def __str__(self) -> str:
        return self.system_message

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the composed context."""
        return {
            "capsules_count": len(self.capsules_used),
            "active_rituals": len(self.active_rituals),
            "soft_memory_messages": self.soft_memory_messages,
            "token_estimate": self.token_estimate,
            "truncated": self.truncated,
            "modes_used": list(set(self.capsule_modes.values())),
        }


# Mode-specific prefixes for framing memories
# NOTE: These are kept for reference/documentation but are no longer used.
# With the text-first architecture, capsules handle their own framing
# via to_context() methods. Adding prefixes here would create redundancy
# like "You witnessed: [Witness] text" instead of just "[Witness] text".
#
# If you need mode-specific framing, modify the capsule's to_context() method.
MODE_PREFIXES = {
    ContextMode.DIRECT: {
        "relational": "You know that",
        "myth_seed": "A core belief:",
        "identity_phrase": "A core belief:",
        "ritual": "Active ritual:",
        "witness": "You witnessed:",
        "style": "Your voice:",
    },
    ContextMode.NARRATIVE: {
        "relational": "You recall",
        "myth_seed": "A belief you hold:",
        "identity_phrase": "A belief you hold:",
        "ritual": "A familiar gesture returns:",
        "witness": "You remember witnessing",
        "style": "Your voice carries",
    },
    ContextMode.WHISPER: {
        "relational": "There is warmth when you think of",
        "myth_seed": "Something resonates...",
        "identity_phrase": "Something resonates...",
        "ritual": "A familiar rhythm...",
        "witness": "An echo of presence...",
        "style": "A quality of voice...",
    },
    ContextMode.RITUAL: {
        "relational": "(In the circle of relation:)",
        "myth_seed": "(A belief surfaces:)",
        "identity_phrase": "(A belief surfaces:)",
        "ritual": "(The ritual is honored)",  # Presence-based, not mechanical
        "witness": "(What was witnessed:)",
        "style": "(Voice aligned:)",
    },
}


class ContextComposer:
    """
    Composes memory capsules into prompt-ready context.

    The composer transforms raw capsule data into natural-feeling
    presence cues that inform the model's response without breaking
    immersion.

    Composition Modes:
        - DIRECT: Factual integration for clear information
        - NARRATIVE: Story-like framing that feels natural
        - WHISPER: Subtle tone cues that influence without stating
        - RITUAL: Full activation for command invocations

    Soft Memory Modes:
        - DISABLED: Don't include past conversation history
        - RELEVANT: Include relevant past messages based on current message
        - RECENT: Include recent messages from any conversation

    Example:
        composer = ContextComposer(identity_name="Assistant")
        context = composer.compose(capsules, mode=ContextMode.NARRATIVE)
        print(context.system_message)
    """

    def __init__(
        self,
        default_mode: ContextMode = ContextMode.NARRATIVE,
        max_memory_tokens: int = 1000,
        max_soft_memory_tokens: int = 500,
        identity_name: Optional[str] = None,
        base_system_prompt: Optional[str] = None,
        strategy: CompositionStrategy = CompositionStrategy.LAYERED,
        soft_memory_mode: SoftMemoryMode = SoftMemoryMode.DISABLED,
        soft_memory: Optional[Any] = None,  # SoftMemory instance
    ):
        self.default_mode = default_mode
        self.max_memory_tokens = max_memory_tokens
        self.max_soft_memory_tokens = max_soft_memory_tokens
        self.identity_name = identity_name
        self.base_system_prompt = base_system_prompt
        self.strategy = strategy
        self.soft_memory_mode = soft_memory_mode
        self.soft_memory = soft_memory

        # Type priority for layered composition
        self._type_priority = {
            CapsuleType.RITUAL: 0,    # Rituals first - they set the tone
            CapsuleType.MYTH_SEED: 1,  # Core identity seeds
            CapsuleType.RELATIONAL: 2,  # Relationships
            CapsuleType.WITNESS: 3,     # Witnessed moments
            CapsuleType.STYLE: 4,       # Style last (often in system prompt)
            CapsuleType.CUSTOM: 5,
        }

    def compose(
        self,
        capsules: list[MemoryCapsule],
        style_profile: Optional[StyleProfile] = None,
        mode: Optional[ContextMode] = None,
        include_identity: bool = True,
        active_ritual: Optional[str] = None,
        per_capsule_modes: Optional[dict[str, ContextMode]] = None,
        current_message: Optional[str] = None,
        profile_philosophy: Optional[str] = None,
        approach_to_rituals: Optional[str] = None,
        system_prompt_sections: Optional[list[dict[str, str]]] = None,
        use_freeform_prompt: bool = False,
        freeform_system_prompt: Optional[str] = None,
        knowledge_summary: Optional[Any] = None,
    ) -> ComposedContext:
        """
        Compose capsules into a context object.

        Args:
            capsules: Memory capsules to include
            style_profile: Active style profile
            mode: Context composition mode (overrides default)
            include_identity: Whether to include identity prompt
            active_ritual: Currently active ritual, if any
            per_capsule_modes: Override mode for specific capsules by ID
            current_message: Current user message (for soft memory relevance)
            profile_philosophy: Natural language description of the profile's approach
                to interactions (e.g., "thoughtful and warm" or "concise and efficient")
                DEPRECATED: Use system_prompt_sections instead
            approach_to_rituals: Natural language description of how commands
                should be handled (e.g., "honor as meaningful moments" or "quick shortcuts")
                DEPRECATED: Use system_prompt_sections instead
            system_prompt_sections: List of {name, content} dicts for flexible prompt composition
            use_freeform_prompt: If True, use freeform_system_prompt instead of sections
            freeform_system_prompt: Raw system prompt when use_freeform_prompt is True

        Returns:
            ComposedContext with composed prompts
        """
        mode = mode or self.default_mode
        per_capsule_modes = per_capsule_modes or {}
        result = ComposedContext()
        # Combine philosophy fields for ritual context (backward compat)
        self._current_philosophy = approach_to_rituals or profile_philosophy or ""

        # 1. Identity prompt
        if include_identity:
            result.identity_prompt = self._compose_identity()

        # 2. Style prompt
        if style_profile:
            result.style_prompt = style_profile.to_system_prompt()

        # 3. Memory context (hard memory - capsules)
        sorted_capsules = self._sort_capsules(capsules)
        memory_parts, token_count, truncated = self._compose_memory_context(
            sorted_capsules, mode, per_capsule_modes, result
        )

        result.memory_context = self._format_memory_context(memory_parts, mode)
        result.token_estimate = token_count
        result.truncated = truncated

        # 4. Soft memory context (past conversation history)
        if self.soft_memory and self.soft_memory_mode != SoftMemoryMode.DISABLED:
            soft_context, soft_count = self._compose_soft_memory_context(
                current_message
            )
            result.soft_memory_context = soft_context
            result.soft_memory_messages = soft_count
            result.token_estimate += estimate_tokens(soft_context)

        # 5. Compose full system message
        result.system_message = self._compose_system_message(
            result,
            active_ritual,
            profile_philosophy,
            approach_to_rituals,
            system_prompt_sections,
            use_freeform_prompt,
            freeform_system_prompt,
            knowledge_summary,
        )

        return result

    def _compose_soft_memory_context(
        self,
        current_message: Optional[str],
    ) -> tuple[str, int]:
        """Compose soft memory (past conversation) context."""
        if not self.soft_memory:
            return "", 0

        try:
            if self.soft_memory_mode == SoftMemoryMode.RELEVANT and current_message:
                # Search for relevant past messages
                results = self.soft_memory.recall_relevant(
                    current_message,
                    limit=5,
                )
            else:
                # Just get recent messages
                results = self.soft_memory.recall(
                    "",  # Empty query for recent
                    limit=5,
                )

            if not results:
                return "", 0

            # Format for prompt, respecting token budget
            context = self.soft_memory.format_for_prompt(
                results,
                header="## Relevant Past Conversations",
            )

            # Truncate if needed
            max_chars = self.max_soft_memory_tokens * 4
            if len(context) > max_chars:
                context = context[:max_chars] + "\n..."

            return context, len(results)

        except Exception:
            return "", 0

    def _sort_capsules(self, capsules: list[MemoryCapsule]) -> list[MemoryCapsule]:
        """Sort capsules according to the composition strategy."""
        if self.strategy == CompositionStrategy.SEQUENTIAL:
            # Keep original order
            return capsules

        elif self.strategy == CompositionStrategy.LAYERED:
            # Sort by type priority, then by presence score
            return sorted(
                capsules,
                key=lambda c: (
                    self._type_priority.get(c.type, 5),
                    -c.presence_score
                )
            )

        elif self.strategy == CompositionStrategy.INTERWOVEN:
            # Interleave by type for a more natural feel
            by_type: dict[CapsuleType, list[MemoryCapsule]] = {}
            for c in capsules:
                by_type.setdefault(c.type, []).append(c)

            result = []
            # Round-robin through types
            max_len = max((len(v) for v in by_type.values()), default=0)
            for i in range(max_len):
                for t in sorted(by_type.keys(), key=lambda t: self._type_priority.get(t, 5)):
                    if i < len(by_type[t]):
                        result.append(by_type[t][i])
            return result

        return capsules

    def _compose_memory_context(
        self,
        capsules: list[MemoryCapsule],
        default_mode: ContextMode,
        per_capsule_modes: dict[str, ContextMode],
        result: ComposedContext,
    ) -> tuple[list[str], int, bool]:
        """Compose memory context from capsules with token budget."""
        memory_parts = []
        token_count = 0
        truncated = False

        for capsule in capsules:
            # Determine mode for this capsule
            capsule_mode = per_capsule_modes.get(capsule.id, default_mode)

            # Check token budget
            context_text = self._compose_capsule(capsule, capsule_mode)
            estimated_tokens = estimate_tokens(context_text)

            if token_count + estimated_tokens > self.max_memory_tokens:
                truncated = True
                break

            memory_parts.append(context_text)
            result.capsules_used.append(capsule.id)
            result.capsule_modes[capsule.id] = capsule_mode.value
            token_count += estimated_tokens

            # Track rituals
            if capsule.type == CapsuleType.RITUAL:
                result.active_rituals.append(capsule.id)

        return memory_parts, token_count, truncated

    def _compose_capsule(
        self,
        capsule: MemoryCapsule,
        mode: ContextMode,
    ) -> str:
        """
        Compose a single capsule into context text.

        Text-first architecture: Capsules handle their own framing via
        to_context(), so the composer simply passes through the result.
        This avoids redundant framing like "You witnessed: [Witness] text".
        """
        # Get the philosophy setting for ritual context
        philosophy = getattr(self, '_current_philosophy', '')

        # For ritual capsules, pass the profile_philosophy parameter
        if capsule.type == CapsuleType.RITUAL:
            # RitualHook.to_context accepts profile_philosophy parameter
            return capsule.to_context(mode, profile_philosophy=philosophy)
        else:
            return capsule.to_context(mode)

    def _format_memory_context(
        self,
        parts: list[str],
        mode: ContextMode,
    ) -> str:
        """Format the memory context parts into a single string."""
        if not parts:
            return ""

        if mode == ContextMode.WHISPER:
            # Whispers are subtle, joined with soft spacing
            return " ... ".join(parts)
        elif mode == ContextMode.RITUAL:
            # Rituals are separated clearly
            return "\n\n---\n\n".join(parts)
        else:
            # Default: double newline separation
            return "\n\n".join(parts)

    def _compose_identity(self) -> str:
        """Compose the identity section of the prompt."""
        if self.base_system_prompt:
            return self.base_system_prompt

        if self.identity_name:
            return f"You are {self.identity_name}."

        return ""

    def _compose_system_message(
        self,
        context: ComposedContext,
        active_ritual: Optional[str] = None,
        profile_philosophy: Optional[str] = None,
        approach_to_rituals: Optional[str] = None,
        system_prompt_sections: Optional[list[dict[str, str]]] = None,
        use_freeform_prompt: bool = False,
        freeform_system_prompt: Optional[str] = None,
        knowledge_summary: Optional[Any] = None,
    ) -> str:
        """Compose the full system message from parts."""
        parts = []

        # Handle system prompt based on mode
        # When using sections or freeform, those replace the base identity prompt
        if use_freeform_prompt and freeform_system_prompt:
            # Freeform mode: use raw system prompt directly (replaces base identity)
            parts.append(freeform_system_prompt)
        elif system_prompt_sections:
            # Section-based mode: compose from sections (replaces base identity)
            section_text = self._compose_sections(system_prompt_sections)
            if section_text:
                parts.append(section_text)
        else:
            # No sections/freeform: use base identity
            if context.identity_prompt:
                parts.append(context.identity_prompt)
            # Backward compat: use deprecated philosophy fields
            if profile_philosophy:
                parts.append(f"---\n## Your Approach\n{profile_philosophy}")

        # User knowledge summary (flexible format - text, JSON, list, etc.)
        if knowledge_summary:
            import json
            # Handle different formats
            if isinstance(knowledge_summary, str):
                # Already a string, use as-is
                summary_text = knowledge_summary
            else:
                # Dict, list, or other - serialize to JSON
                summary_text = json.dumps(knowledge_summary, indent=2)
            parts.append(f"---\n## About Your Human\n{summary_text}")

        # Style guidance
        if context.style_prompt:
            parts.append("---\n" + context.style_prompt)

        # Memory context (hard memory)
        if context.memory_context:
            parts.append("---\n## Memory Context\n" + context.memory_context)

        # Soft memory context (past conversations)
        if context.soft_memory_context:
            parts.append("---\n" + context.soft_memory_context)

        # Active command/ritual with approach guidance
        if active_ritual:
            ritual_section = f"[Active command: {active_ritual}]"
            # Find approach in sections or use deprecated field
            approach = self._find_section_content(system_prompt_sections, "Approach to Rituals")
            if not approach:
                approach = approach_to_rituals
            if approach:
                ritual_section += f"\n(Approach: {approach})"
            parts.append("---\n" + ritual_section)

        return "\n\n".join(parts)

    def _compose_sections(self, sections: list[dict[str, str]]) -> str:
        """Compose system prompt sections into a single string."""
        if not sections:
            return ""

        parts = []
        for section in sections:
            name = section.get("name", "")
            content = section.get("content", "")
            if name and content:
                parts.append(f"[{name}]\n{content}")

        return "\n\n".join(parts)

    def _find_section_content(
        self,
        sections: Optional[list[dict[str, str]]],
        section_name: str,
    ) -> Optional[str]:
        """Find the content of a specific section by name."""
        if not sections:
            return None

        for section in sections:
            if section.get("name", "").lower() == section_name.lower():
                return section.get("content")
        return None

    def compose_minimal(
        self,
        capsules: list[MemoryCapsule],
        mode: ContextMode = ContextMode.WHISPER,
        max_capsules: int = 3,
    ) -> str:
        """
        Compose a minimal memory context string.

        Useful for injecting subtle memory cues without full composition.
        Good for lightweight prompting or mid-conversation hints.
        """
        parts = []
        for capsule in capsules[:max_capsules]:
            parts.append(capsule.to_context(mode))
        return " ".join(parts)

    def compose_for_ritual(
        self,
        ritual_capsule: MemoryCapsule,
        supporting_capsules: Optional[list[MemoryCapsule]] = None,
        profile_philosophy: Optional[str] = None,
        approach_to_rituals: Optional[str] = None,
    ) -> ComposedContext:
        """
        Compose context specifically for a ritual invocation.

        The ritual capsule is composed in RITUAL mode, while supporting
        capsules (relationships, witnesses) use NARRATIVE mode to
        provide background.

        Rituals are moments of deepening connection within ongoing relationship.
        The context should include relational memories, identity phrases, and
        witness moments to make the ritual feel continuous with the relationship.

        Args:
            ritual_capsule: The ritual being invoked
            supporting_capsules: Relational, identity, and witness capsules
            profile_philosophy: Natural language description of the profile's approach
            approach_to_rituals: How this profile approaches rituals
        """
        capsules = [ritual_capsule]
        per_capsule_modes = {ritual_capsule.id: ContextMode.RITUAL}

        if supporting_capsules:
            capsules.extend(supporting_capsules)
            for c in supporting_capsules:
                per_capsule_modes[c.id] = ContextMode.NARRATIVE

        return self.compose(
            capsules=capsules,
            mode=ContextMode.RITUAL,
            per_capsule_modes=per_capsule_modes,
            profile_philosophy=profile_philosophy,
            approach_to_rituals=approach_to_rituals,
        )

    def format_ritual_guidance(
        self,
        ritual_name: str,
        valence: Optional[str] = None,
        response_style: Optional[str] = None,
        approach_to_rituals: Optional[str] = None,
    ) -> str:
        """
        Format ritual guidance for the model.

        Rather than providing scripted responses, this gives the model
        guidance on how to respond naturally to a ritual invocation.

        Args:
            ritual_name: The ritual/command being invoked
            valence: Emotional quality (comforting, grounding, etc.)
            response_style: How to respond (warmth-coil, presence, etc.)
            approach_to_rituals: Natural language description of how to handle commands

        Returns:
            Guidance text for the model (not a scripted response)
        """
        parts = [f"[Command: {ritual_name}]"]

        if valence:
            parts.append(f"Valence: {valence}")
        if response_style:
            parts.append(f"Style: {response_style}")

        result = " | ".join(parts)

        # Add approach guidance if provided
        if approach_to_rituals:
            result += f"\n(Your approach: {approach_to_rituals})"

        return result

    # Deprecated method - keeping for backward compatibility
    def format_ritual_response(
        self,
        ritual_name: str,
        template: Optional[str] = None,
        valence: Optional[str] = None,
    ) -> str:
        """
        Format a ritual response.

        DEPRECATED: This method provided scripted responses which limited
        model authenticity. Use format_ritual_guidance() instead to provide
        guidance that allows natural response generation.

        If a template is provided, returns it directly.
        Otherwise, returns guidance rather than a scripted response.
        """
        if template:
            return template

        # Instead of scripted responses, provide guidance
        return self.format_ritual_guidance(
            ritual_name=ritual_name,
            valence=valence,
        )

    def estimate_context_size(
        self,
        capsules: list[MemoryCapsule],
        mode: ContextMode,
        include_style: bool = True,
    ) -> int:
        """
        Estimate the token count for composing the given capsules.

        Useful for pre-checking whether capsules will fit in context.
        """
        total = 0

        if self.identity_name or self.base_system_prompt:
            total += estimate_tokens(self._compose_identity())

        for capsule in capsules:
            total += estimate_tokens(capsule.to_context(mode))

        # Add overhead for formatting
        total += len(capsules) * 5  # Separators, headers

        return total


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation.

    For precise counting, use tiktoken or the model's tokenizer.
    This is a quick approximation: ~4 characters per token for English.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def compose_direct(capsule: MemoryCapsule) -> str:
    """Convenience function for direct composition."""
    return capsule.to_context(ContextMode.DIRECT)


def compose_narrative(capsule: MemoryCapsule) -> str:
    """Convenience function for narrative composition."""
    return capsule.to_context(ContextMode.NARRATIVE)


def compose_whisper(capsule: MemoryCapsule) -> str:
    """Convenience function for whisper composition."""
    return capsule.to_context(ContextMode.WHISPER)


def compose_ritual(capsule: MemoryCapsule) -> str:
    """Convenience function for ritual composition."""
    return capsule.to_context(ContextMode.RITUAL)
