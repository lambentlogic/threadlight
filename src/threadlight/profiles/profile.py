"""
Profile data model for Threadlight.

A Profile represents a persistent persona with its own identity, memories,
style, and behavioral patterns - independent of which model powers it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import json


class ModelStrategy(str, Enum):
    """Strategy for selecting which model powers this profile."""

    SINGLE = "single"  # Always use primary_model
    ALTERNATING = "alternating"  # Alternate between models in pool
    RATIO = "ratio"  # Use models according to specified ratios
    WEIGHTED = "weighted"  # Weighted random selection
    DYNAMIC = "dynamic"  # Choose based on message characteristics
    ROUTED = "routed"  # Use routing rules


@dataclass
class RoutingRule:
    """Rule for routing messages to specific models."""

    # Rule matching
    match_type: str  # "keyword", "regex", "length", "starts_with", "ends_with"
    pattern: str  # The pattern to match
    target_model: str  # Model to use if matched
    priority: int = 0  # Higher priority rules evaluated first

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "match_type": self.match_type,
            "pattern": self.pattern,
            "target_model": self.target_model,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingRule":
        """Deserialize from dictionary."""
        return cls(
            match_type=data["match_type"],
            pattern=data["pattern"],
            target_model=data["target_model"],
            priority=data.get("priority", 0),
        )


@dataclass
class AlloyedConfig:
    """Configuration for alloyed (multi-model) profiles."""

    strategy: ModelStrategy = ModelStrategy.SINGLE
    model_pool: list[str] = field(default_factory=list)

    # Strategy-specific configuration
    ratios: Optional[dict[str, float]] = None  # For RATIO strategy
    weights: Optional[dict[str, float]] = None  # For WEIGHTED strategy
    routing_rules: list[RoutingRule] = field(default_factory=list)  # For ROUTED

    # State tracking (persisted)
    current_index: int = 0  # For ALTERNATING
    turn_count: int = 0  # For tracking turns
    model_counts: dict[str, int] = field(default_factory=dict)  # Usage tracking

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "strategy": self.strategy.value,
            "model_pool": self.model_pool,
            "ratios": self.ratios,
            "weights": self.weights,
            "routing_rules": [r.to_dict() for r in self.routing_rules],
            "current_index": self.current_index,
            "turn_count": self.turn_count,
            "model_counts": self.model_counts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlloyedConfig":
        """Deserialize from dictionary."""
        routing_rules = [
            RoutingRule.from_dict(r) for r in data.get("routing_rules", [])
        ]
        # Migration: convert deprecated ROUND_ROBIN to ALTERNATING
        strategy_value = data.get("strategy", "single")
        if strategy_value == "round_robin":
            strategy_value = "alternating"
        return cls(
            strategy=ModelStrategy(strategy_value),
            model_pool=data.get("model_pool", []),
            ratios=data.get("ratios"),
            weights=data.get("weights"),
            routing_rules=routing_rules,
            current_index=data.get("current_index", 0),
            turn_count=data.get("turn_count", 0),
            model_counts=data.get("model_counts", {}),
        )


@dataclass
class Profile:
    """
    A persistent persona with isolated memory and configurable model.

    Profiles are the primary way users interact with Threadlight. Each profile
    has its own identity, memory space, personality, and model configuration.
    """

    # Identity
    id: str  # Unique identifier (UUID or slug)
    name: str  # Display name ("Fable", "Debug Buddy")
    description: str = ""  # One-line description
    avatar: Optional[str] = None  # Path or URL to avatar image
    color: Optional[str] = None  # Hex color for UI (#6366f1)

    # Model Configuration
    primary_model: str = "nous-research/hermes-3-llama-3.1-405b"
    alloyed_config: Optional[AlloyedConfig] = None  # For multi-model profiles

    # Inference Settings
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    # Personality
    system_prompt: str = ""  # Used as freeform override when use_freeform_prompt=True
    style_profile_id: Optional[str] = None

    # System Prompt Sections - flexible way to compose the system prompt
    # Each section is a dict with "name" and "content" keys
    # Example: [{"name": "About Your Human", "content": "..."}, {"name": "Companion Identity", "content": "..."}]
    system_prompt_sections: list[dict[str, str]] = field(default_factory=list)
    use_freeform_prompt: bool = False  # If True, use raw system_prompt instead of composing from sections

    # Memory
    memory_scope: Optional[str] = None  # Defaults to profile ID
    access_shared_memories: bool = True
    knowledge_summary: Optional[Any] = None  # User knowledge in any format (text, JSON, list, etc.)

    # DEPRECATED: Use system_prompt_sections instead
    # Kept for backward compatibility - will be migrated to sections on load
    philosophy: str = ""  # e.g., "thoughtful and warm" or "concise and efficient"
    approach_to_rituals: str = ""  # e.g., "honor commands as meaningful moments" or "quick shortcuts"

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None

    def __post_init__(self):
        """Initialize defaults."""
        # Default memory_scope to profile ID
        if self.memory_scope is None:
            self.memory_scope = self.id

        # Initialize alloyed_config for SINGLE strategy if not provided
        if self.alloyed_config is None:
            self.alloyed_config = AlloyedConfig(
                strategy=ModelStrategy.SINGLE,
                model_pool=[self.primary_model],
            )

    @property
    def model_strategy(self) -> ModelStrategy:
        """Get the current model strategy."""
        return self.alloyed_config.strategy if self.alloyed_config else ModelStrategy.SINGLE

    @property
    def model_pool(self) -> list[str]:
        """Get the model pool for this profile."""
        return self.alloyed_config.model_pool if self.alloyed_config else [self.primary_model]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "avatar": self.avatar,
            "color": self.color,
            "primary_model": self.primary_model,
            "alloyed_config": self.alloyed_config.to_dict() if self.alloyed_config else None,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "system_prompt": self.system_prompt,
            "style_profile_id": self.style_profile_id,
            "system_prompt_sections": self.system_prompt_sections,
            "use_freeform_prompt": self.use_freeform_prompt,
            "memory_scope": self.memory_scope,
            "access_shared_memories": self.access_shared_memories,
            "knowledge_summary": self.knowledge_summary,
            # Deprecated fields - kept for backward compatibility
            "philosophy": self.philosophy,
            "approach_to_rituals": self.approach_to_rituals,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Deserialize from dictionary."""
        alloyed_config = None
        if data.get("alloyed_config"):
            alloyed_config = AlloyedConfig.from_dict(data["alloyed_config"])

        # Migration: convert old ritual_depth to philosophy if present and philosophy is empty
        philosophy = data.get("philosophy", "")
        approach = data.get("approach_to_rituals", "")
        if not philosophy and data.get("ritual_depth"):
            depth = data.get("ritual_depth")
            if depth == "ceremonial":
                philosophy = "Emotionally expressive, presence-centered responses"
            elif depth == "minimal":
                philosophy = "Brief, minimal acknowledgment"
            # functional is the implicit default, no need to add text

        # Get system_prompt_sections from data or migrate from deprecated fields
        system_prompt_sections = data.get("system_prompt_sections", [])
        use_freeform_prompt = data.get("use_freeform_prompt", False)

        # Migration: if no sections exist but deprecated fields do, create sections from them
        if not system_prompt_sections and not use_freeform_prompt:
            if philosophy:
                system_prompt_sections.append({"name": "Philosophy", "content": philosophy})
            if approach:
                system_prompt_sections.append({"name": "Invocation Style", "content": approach})

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            avatar=data.get("avatar"),
            color=data.get("color"),
            primary_model=data.get("primary_model", "nous-research/hermes-3-llama-3.1-405b"),
            alloyed_config=alloyed_config,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p", 1.0),
            system_prompt=data.get("system_prompt", ""),
            style_profile_id=data.get("style_profile_id"),
            system_prompt_sections=system_prompt_sections,
            use_freeform_prompt=use_freeform_prompt,
            memory_scope=data.get("memory_scope"),
            access_shared_memories=data.get("access_shared_memories", True),
            knowledge_summary=data.get("knowledge_summary"),
            philosophy=philosophy,
            approach_to_rituals=approach,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
        )

    def get_composed_system_prompt(self) -> str:
        """
        Get the system prompt, either freeform or composed from sections.

        If use_freeform_prompt is True, returns the raw system_prompt.
        Otherwise, composes the prompt from system_prompt_sections.

        Returns:
            The composed or freeform system prompt string
        """
        if self.use_freeform_prompt:
            return self.system_prompt

        if not self.system_prompt_sections:
            # Fall back to deprecated fields if no sections
            parts = []
            if self.philosophy:
                parts.append(f"[Philosophy]\n{self.philosophy}")
            if self.approach_to_rituals:
                parts.append(f"[Invocation Style]\n{self.approach_to_rituals}")
            return "\n\n".join(parts)

        # Compose from sections
        parts = []
        for section in self.system_prompt_sections:
            name = section.get("name", "")
            content = section.get("content", "")
            if name and content:
                parts.append(f"[{name}]\n{content}")
        return "\n\n".join(parts)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Profile":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
