"""
Decay engine for memory presence scores.

Memories fade over time unless reinforced through access.
Sacred memories never decay. This is consentful forgetting.

Decay strategies:
- Time-based: Memories fade based on last access or creation time
- Reinforcement-based: Access count and presence score affect decay
- Relationship-based: Connected capsules decay together

Retention policies:
- SACRED: Never decays, requires explicit deletion
- NORMAL: Standard decay, reinforced by access
- EPHEMERAL: Rapid decay, session-scoped
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
import logging
import math

from threadlight.capsules.base import MemoryCapsule, RetentionPolicy, CapsuleType
from threadlight.storage.base import StorageBackend, CapsuleFilter

logger = logging.getLogger(__name__)


class DecayStrategy(ABC):
    """Abstract base class for decay strategies."""

    @abstractmethod
    def calculate_decay(
        self,
        capsule: MemoryCapsule,
        current_time: datetime,
    ) -> float:
        """
        Calculate the new presence score for a capsule.

        Args:
            capsule: The capsule to decay
            current_time: Current timestamp

        Returns:
            New presence score (0.0 to 1.0)
        """
        pass

    def calculate_reinforcement(
        self,
        capsule: MemoryCapsule,
        strength: float = 0.2,
    ) -> float:
        """
        Calculate reinforcement boost for a capsule.

        Args:
            capsule: The capsule to reinforce
            strength: Base reinforcement strength (0.0 to 1.0)

        Returns:
            New presence score after reinforcement
        """
        # Default implementation: boost presence by strength, capped at 1.0
        new_score = capsule.presence_score + strength
        return min(1.0, new_score)


class LinearDecayStrategy(DecayStrategy):
    """
    Simple linear decay based on time since last access.

    presence_score decreases linearly with time, modified by:
    - decay_rate: how fast the capsule decays
    - access_count: reinforcement bonus for frequently accessed memories
    """

    def __init__(
        self,
        base_period_days: int = 30,
        access_bonus_factor: float = 0.02,
        max_access_bonus: float = 0.3,
    ):
        self.base_period_days = base_period_days
        self.access_bonus_factor = access_bonus_factor
        self.max_access_bonus = max_access_bonus

    def calculate_decay(
        self,
        capsule: MemoryCapsule,
        current_time: datetime,
    ) -> float:
        # Sacred memories never decay
        if capsule.retention == RetentionPolicy.SACRED:
            return capsule.presence_score

        # Calculate time since last access
        time_since_access = current_time - capsule.last_accessed
        days_since_access = time_since_access.total_seconds() / 86400

        # Base decay amount
        decay_amount = capsule.decay_rate * (days_since_access / self.base_period_days)

        # Ephemeral memories decay faster
        if capsule.retention == RetentionPolicy.EPHEMERAL:
            decay_amount *= 3.0

        # Access reinforcement bonus (slows decay)
        access_bonus = min(
            capsule.access_count * self.access_bonus_factor,
            self.max_access_bonus
        )
        decay_amount = max(0, decay_amount - access_bonus)

        # Calculate new score
        # Decay linearly from 1.0 (full strength when last accessed)
        # rather than compounding from current score
        new_score = 1.0 - decay_amount

        # Clamp to valid range
        return max(0.0, min(1.0, new_score))


class ExponentialDecayStrategy(DecayStrategy):
    """
    Exponential decay -- memories fade faster as they age.

    Good for modeling the "forgetting curve" more realistically.
    The Ebbinghaus forgetting curve suggests exponential decay
    with reinforcement through spaced repetition.
    """

    def __init__(
        self,
        half_life_days: int = 14,
        min_score: float = 0.1,
    ):
        self.half_life_days = half_life_days
        self.min_score = min_score

    def calculate_decay(
        self,
        capsule: MemoryCapsule,
        current_time: datetime,
    ) -> float:
        if capsule.retention == RetentionPolicy.SACRED:
            return capsule.presence_score

        time_since_access = current_time - capsule.last_accessed
        days_since_access = time_since_access.total_seconds() / 86400

        # Adjust half-life based on decay_rate and access_count
        # More accesses = slower decay (longer effective half-life)
        access_factor = 1 + (capsule.access_count * 0.1)
        effective_half_life = (self.half_life_days * access_factor) / (capsule.decay_rate + 0.1)

        # Ephemeral memories have much shorter half-life
        if capsule.retention == RetentionPolicy.EPHEMERAL:
            effective_half_life /= 3

        # Exponential decay formula
        decay_factor = math.pow(0.5, days_since_access / effective_half_life)
        new_score = capsule.presence_score * decay_factor

        # Don't decay below minimum
        return max(self.min_score, new_score)


class RelationshipDecayStrategy(DecayStrategy):
    """
    Relationship-aware decay strategy.

    Connected capsules influence each other's decay:
    - When one memory in a cluster is accessed, related memories decay slower
    - Orphan memories (no relationships) decay faster
    - Strong relationship bonds create decay resistance

    This models how real memory works -- memories that are part of
    a rich associative network are more resistant to forgetting.
    """

    def __init__(
        self,
        base_half_life_days: int = 21,
        relationship_bonus: float = 0.15,
        orphan_penalty: float = 1.5,
        min_score: float = 0.05,
    ):
        self.base_half_life_days = base_half_life_days
        self.relationship_bonus = relationship_bonus
        self.orphan_penalty = orphan_penalty
        self.min_score = min_score

        # Cache for relationship graph (capsule_id -> [related_ids])
        self._relationships: dict[str, list[str]] = {}

    def set_relationships(self, relationships: dict[str, list[str]]) -> None:
        """Set the relationship graph for decay calculations."""
        self._relationships = relationships

    def get_relationship_strength(self, capsule_id: str) -> float:
        """
        Calculate relationship strength for a capsule.

        Returns a multiplier: >1 means more connections = slower decay.
        """
        related = self._relationships.get(capsule_id, [])
        if not related:
            return 1.0 / self.orphan_penalty  # Orphans decay faster

        # More relationships = stronger resistance to decay
        # Diminishing returns after a point
        num_relations = len(related)
        return 1.0 + (self.relationship_bonus * math.log(num_relations + 1))

    def calculate_decay(
        self,
        capsule: MemoryCapsule,
        current_time: datetime,
    ) -> float:
        if capsule.retention == RetentionPolicy.SACRED:
            return capsule.presence_score

        time_since_access = current_time - capsule.last_accessed
        days_since_access = time_since_access.total_seconds() / 86400

        # Relationship strength affects half-life
        rel_strength = self.get_relationship_strength(capsule.id)
        effective_half_life = self.base_half_life_days * rel_strength

        # Adjust for decay rate and retention policy
        if capsule.retention == RetentionPolicy.EPHEMERAL:
            effective_half_life /= 3

        effective_half_life /= (capsule.decay_rate + 0.1)

        # Exponential decay
        decay_factor = math.pow(0.5, days_since_access / effective_half_life)
        new_score = capsule.presence_score * decay_factor

        return max(self.min_score, new_score)

    def calculate_reinforcement(
        self,
        capsule: MemoryCapsule,
        strength: float = 0.2,
    ) -> float:
        """
        Reinforcement with relationship bonus.

        Well-connected memories gain more from reinforcement.
        """
        rel_strength = self.get_relationship_strength(capsule.id)
        effective_strength = strength * rel_strength

        new_score = capsule.presence_score + effective_strength
        return min(1.0, new_score)


@dataclass
class DecayResult:
    """Result of a decay cycle."""

    capsules_processed: int
    capsules_decayed: int
    capsules_dormant: int  # Reached minimum presence
    capsules_reinforced: int = 0  # Touched during cycle
    updates: dict[str, float] = field(default_factory=dict)  # capsule_id -> new_score
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for logging/API."""
        return {
            "processed": self.capsules_processed,
            "decayed": self.capsules_decayed,
            "dormant": self.capsules_dormant,
            "reinforced": self.capsules_reinforced,
            "updates_count": len(self.updates),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReinforcementResult:
    """Result of reinforcing memories."""

    capsules_reinforced: int
    old_scores: dict[str, float]  # capsule_id -> old_score
    new_scores: dict[str, float]  # capsule_id -> new_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "reinforced": self.capsules_reinforced,
            "changes": {
                cid: {
                    "old": self.old_scores.get(cid, 0),
                    "new": self.new_scores.get(cid, 0),
                }
                for cid in self.new_scores
            }
        }


class DecayEngine:
    """
    Engine for processing memory decay.

    Runs periodically to reduce presence scores of unaccessed memories.
    Supports multiple decay strategies and relationship-aware decay.

    Example:
        engine = DecayEngine(storage, strategy=ExponentialDecayStrategy())

        # Run decay cycle
        result = engine.run_decay_cycle()
        print(f"Decayed {result.capsules_decayed} memories")

        # Reinforce specific memories
        engine.reinforce(["capsule-id-1", "capsule-id-2"], strength=0.3)
    """

    def __init__(
        self,
        storage: StorageBackend,
        strategy: Optional[DecayStrategy] = None,
        decay_threshold: float = 0.1,  # Below this, capsule is "dormant"
        min_age_hours: int = 24,  # Don't decay very recent memories
        enable_relationship_decay: bool = False,
    ):
        self.storage = storage
        self.strategy = strategy or LinearDecayStrategy()
        self.decay_threshold = decay_threshold
        self.min_age_hours = min_age_hours
        self.enable_relationship_decay = enable_relationship_decay

        # Tracking
        self._last_cycle: Optional[datetime] = None
        self._cycle_count: int = 0

    def calculate_decay_score(
        self,
        capsule: MemoryCapsule,
        current_time: Optional[datetime] = None,
    ) -> float:
        """
        Calculate the decay score for a single capsule.

        This does not modify the capsule -- it just calculates what
        the new score would be after decay.

        Args:
            capsule: The capsule to calculate decay for
            current_time: Override timestamp (defaults to now)

        Returns:
            The calculated new presence score
        """
        current_time = current_time or datetime.utcnow()
        return self.strategy.calculate_decay(capsule, current_time)

    def run_decay_cycle(self, current_time: Optional[datetime] = None) -> DecayResult:
        """
        Run a decay cycle on all eligible capsules.

        Args:
            current_time: Override for testing (defaults to now)

        Returns:
            DecayResult with statistics
        """
        current_time = current_time or datetime.utcnow()
        self._last_cycle = current_time
        self._cycle_count += 1

        # Update relationship graph if using relationship decay
        if self.enable_relationship_decay and isinstance(self.strategy, RelationshipDecayStrategy):
            self._update_relationship_graph()

        # Get capsules eligible for decay
        cutoff_time = current_time - timedelta(hours=self.min_age_hours)
        capsules = self.storage.get_capsules_for_decay(
            before=cutoff_time,
            exclude_retention=[RetentionPolicy.SACRED]
        )

        result = DecayResult(
            capsules_processed=len(capsules),
            capsules_decayed=0,
            capsules_dormant=0,
            updates={},
            timestamp=current_time,
        )

        for capsule in capsules:
            old_score = capsule.presence_score
            new_score = self.strategy.calculate_decay(capsule, current_time)

            if new_score < old_score:
                result.capsules_decayed += 1
                result.updates[capsule.id] = new_score

                if new_score <= self.decay_threshold:
                    result.capsules_dormant += 1

        # Batch update presence scores
        if result.updates:
            self.storage.update_presence_scores(result.updates)
            logger.info(
                f"Decay cycle #{self._cycle_count}: {result.capsules_decayed} decayed, "
                f"{result.capsules_dormant} dormant"
            )

        return result

    # Alias for backward compatibility
    run_cycle = run_decay_cycle

    def reinforce(
        self,
        capsule_ids: list[str],
        strength: float = 0.2,
        propagate_to_related: bool = False,
    ) -> ReinforcementResult:
        """
        Reinforce specific memories to strengthen their presence.

        This is the inverse of decay -- explicitly strengthening memories
        that should be retained.

        Args:
            capsule_ids: IDs of capsules to reinforce
            strength: Reinforcement strength (0.0 to 1.0)
            propagate_to_related: If True, also reinforce related capsules

        Returns:
            ReinforcementResult with statistics
        """
        result = ReinforcementResult(
            capsules_reinforced=0,
            old_scores={},
            new_scores={},
        )

        # Expand to related capsules if requested
        if propagate_to_related and self.enable_relationship_decay:
            if isinstance(self.strategy, RelationshipDecayStrategy):
                expanded_ids = set(capsule_ids)
                for cid in capsule_ids:
                    related = self.strategy._relationships.get(cid, [])
                    expanded_ids.update(related)
                capsule_ids = list(expanded_ids)

        updates = {}
        for cid in capsule_ids:
            capsule = self.storage.get_capsule(cid)
            if capsule is None:
                continue

            # Skip sacred (already max presence conceptually)
            if capsule.retention == RetentionPolicy.SACRED:
                continue

            old_score = capsule.presence_score
            new_score = self.strategy.calculate_reinforcement(capsule, strength)

            if new_score > old_score:
                result.capsules_reinforced += 1
                result.old_scores[cid] = old_score
                result.new_scores[cid] = new_score
                updates[cid] = new_score

                # Also touch the capsule
                capsule.touch()
                capsule.presence_score = new_score
                self.storage.update_capsule(capsule)

        logger.info(f"Reinforced {result.capsules_reinforced} capsules with strength {strength}")
        return result

    def touch_capsule(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """
        Touch a capsule to refresh its presence.

        This is called when a capsule is accessed, reinforcing it.
        """
        capsule = self.storage.get_capsule(capsule_id)
        if capsule is None:
            return None

        capsule.touch()
        self.storage.update_capsule(capsule)
        return capsule

    def revive_capsule(
        self,
        capsule_id: str,
        new_score: float = 1.0
    ) -> Optional[MemoryCapsule]:
        """
        Revive a dormant capsule to full presence.

        Use when a user explicitly wants to restore a faded memory.
        """
        capsule = self.storage.get_capsule(capsule_id)
        if capsule is None:
            return None

        capsule.presence_score = new_score
        capsule.touch()
        self.storage.update_capsule(capsule)

        logger.info(f"Revived capsule {capsule_id} to presence {new_score}")
        return capsule

    def get_dormant_capsules(self) -> list[MemoryCapsule]:
        """Get all capsules that have decayed to dormant state."""
        filter = CapsuleFilter(
            min_presence_score=0.0,
            consent_confirmed=True,
        )
        all_capsules = self.storage.list_capsules(filter)

        return [c for c in all_capsules if c.presence_score <= self.decay_threshold]

    def get_near_dormant(self, threshold_buffer: float = 0.1) -> list[MemoryCapsule]:
        """
        Get capsules that are close to becoming dormant.

        Useful for alerting users about memories that might fade.
        """
        filter = CapsuleFilter(
            min_presence_score=self.decay_threshold,
            consent_confirmed=True,
        )
        all_capsules = self.storage.list_capsules(filter)

        upper_bound = self.decay_threshold + threshold_buffer
        return [
            c for c in all_capsules
            if self.decay_threshold < c.presence_score <= upper_bound
        ]

    def _update_relationship_graph(self) -> None:
        """
        Update the relationship graph for relationship-aware decay.

        This builds a graph based on:
        - Relational capsules (entity mentions)
        - Shared cue phrases
        - Co-accessed capsules (TODO: track in storage)
        """
        if not isinstance(self.strategy, RelationshipDecayStrategy):
            return

        relationships: dict[str, list[str]] = {}

        # Get all capsules
        all_capsules = self.storage.list_capsules(CapsuleFilter(limit=10000))

        # Build relationship graph from relational capsules and cue phrases
        entity_to_capsules: dict[str, list[str]] = {}
        cue_to_capsules: dict[str, list[str]] = {}

        for capsule in all_capsules:
            # Track by entity for relational capsules
            if capsule.type == CapsuleType.RELATIONAL and hasattr(capsule, 'entity'):
                entity = capsule.entity.lower()
                entity_to_capsules.setdefault(entity, []).append(capsule.id)

            # Track by cue phrases
            for cue in capsule.cue_phrases:
                cue_lower = cue.lower()
                cue_to_capsules.setdefault(cue_lower, []).append(capsule.id)

        # Build relationships from shared entities
        for entity, capsule_ids in entity_to_capsules.items():
            if len(capsule_ids) > 1:
                for cid in capsule_ids:
                    related = [other for other in capsule_ids if other != cid]
                    relationships.setdefault(cid, []).extend(related)

        # Build relationships from shared cues
        for cue, capsule_ids in cue_to_capsules.items():
            if len(capsule_ids) > 1:
                for cid in capsule_ids:
                    related = [other for other in capsule_ids if other != cid]
                    relationships.setdefault(cid, []).extend(related)

        # Deduplicate
        for cid in relationships:
            relationships[cid] = list(set(relationships[cid]))

        self.strategy.set_relationships(relationships)

    def get_decay_stats(self) -> dict[str, Any]:
        """Get statistics about the decay engine."""
        dormant = self.get_dormant_capsules()
        near_dormant = self.get_near_dormant()

        return {
            "strategy": type(self.strategy).__name__,
            "decay_threshold": self.decay_threshold,
            "min_age_hours": self.min_age_hours,
            "cycle_count": self._cycle_count,
            "last_cycle": self._last_cycle.isoformat() if self._last_cycle else None,
            "dormant_count": len(dormant),
            "near_dormant_count": len(near_dormant),
            "relationship_decay_enabled": self.enable_relationship_decay,
        }


# Strategy registry for custom strategies
_strategy_registry: dict[str, type[DecayStrategy]] = {
    "linear": LinearDecayStrategy,
    "exponential": ExponentialDecayStrategy,
    "relationship": RelationshipDecayStrategy,
}


def register_strategy(name: str):
    """Decorator to register a custom decay strategy."""
    def decorator(cls: type[DecayStrategy]) -> type[DecayStrategy]:
        _strategy_registry[name] = cls
        return cls
    return decorator


def get_strategy(name: str, **kwargs) -> DecayStrategy:
    """Get a decay strategy by name."""
    if name not in _strategy_registry:
        raise ValueError(f"Unknown decay strategy: {name}")
    return _strategy_registry[name](**kwargs)


def list_strategies() -> list[str]:
    """List all registered decay strategies."""
    return list(_strategy_registry.keys())
