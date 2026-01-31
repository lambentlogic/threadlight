# Resonance-Based Memory Activation: Implementation Plan

This document provides step-by-step implementation guidance for the resonance architecture described in `RESONANCE_ARCHITECTURE.md`.

---

## Files to Create

### New Module: `src/threadlight/resonance/`

```
resonance/
    __init__.py           # Public API exports
    types.py              # Data classes (ToneResult, ResonanceScore, etc.)
    tone.py               # ToneAnalyzer implementation
    entities.py           # EntityExtractor implementation
    engine.py             # ResonanceEngine implementation
```

---

## Phase 1: Type Definitions and ToneAnalyzer

### Step 1.1: Create `resonance/types.py`

```python
"""
Type definitions for the resonance system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToneResult:
    """Result of emotional tone analysis."""

    primary_tone: str  # Dominant detected emotion
    confidence: float  # 0.0-1.0 confidence in primary_tone
    detected_tones: dict[str, float]  # All detected tones with scores

    def has_tone(self, tone: str, threshold: float = 0.3) -> bool:
        """Check if a specific tone was detected above threshold."""
        return self.detected_tones.get(tone, 0.0) >= threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_tone": self.primary_tone,
            "confidence": round(self.confidence, 3),
            "detected_tones": {k: round(v, 3) for k, v in self.detected_tones.items()},
        }


@dataclass
class EntityMention:
    """A mention of a person or entity in a message."""

    name: str
    confidence: float  # 0.0-1.0
    relation_type: str  # "known", "possessive", "reference", etc.

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 3),
            "relation_type": self.relation_type,
        }


@dataclass
class ResonanceScore:
    """Breakdown of resonance scoring for a single capsule."""

    capsule_id: str
    total: float = 0.0
    keyword: float = 0.0
    semantic: float = 0.0
    emotional: float = 0.0
    relational: float = 0.0
    temporal: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "total": round(self.total, 3),
            "components": {
                "keyword": round(self.keyword, 3),
                "semantic": round(self.semantic, 3),
                "emotional": round(self.emotional, 3),
                "relational": round(self.relational, 3),
                "temporal": round(self.temporal, 3),
            }
        }


@dataclass
class ResonanceContext:
    """Context for resonance scoring."""

    message: str
    tone: ToneResult
    entities: list[EntityMention] = field(default_factory=list)
    message_embedding: Optional[list[float]] = None
    recent_capsule_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message[:100] + "..." if len(self.message) > 100 else self.message,
            "tone": self.tone.to_dict(),
            "entities": [e.to_dict() for e in self.entities],
            "has_embedding": self.message_embedding is not None,
            "recent_capsules": len(self.recent_capsule_ids),
        }
```

### Step 1.2: Create `resonance/tone.py`

```python
"""
Emotional tone analysis for resonance-based memory retrieval.
"""

from __future__ import annotations

import re
from typing import Optional

from threadlight.resonance.types import ToneResult


class ToneAnalyzer:
    """
    Analyze emotional tone of messages using lexicon-based detection.

    This is the fast, dependency-free implementation suitable for
    real-time message processing. For more nuanced analysis, see
    the embedding-based approach in ResonanceEngine.
    """

    # Emotion clusters with associated terms
    # Each term can have an optional weight modifier (default 1.0)
    EMOTION_LEXICON: dict[str, dict] = {
        "struggle": {
            "terms": [
                "struggling", "hard", "difficult", "frustrated", "stuck",
                "confused", "lost", "overwhelmed", "tired", "exhausted",
                "can't", "unable", "failing", "fail", "impossible",
                "broken", "defeated", "helpless", "hopeless",
            ],
            "weight": 1.0,
        },
        "joy": {
            "terms": [
                "happy", "excited", "wonderful", "amazing", "grateful",
                "love", "beautiful", "delighted", "thrilled", "fantastic",
                "great", "awesome", "brilliant", "joyful", "ecstatic",
            ],
            "weight": 1.0,
        },
        "grief": {
            "terms": [
                "sad", "miss", "lost", "gone", "passed", "mourning",
                "grieving", "heartbroken", "devastated", "empty",
                "alone", "lonely", "painful", "hurting", "ache",
            ],
            "weight": 1.0,
        },
        "reflection": {
            "terms": [
                "thinking", "wondering", "considering", "remember",
                "realize", "understand", "feel", "sense", "pondering",
                "contemplating", "reflecting", "processing", "looking back",
            ],
            "weight": 0.8,  # Lower weight - reflection often co-occurs
        },
        "seeking_comfort": {
            "terms": [
                "need", "help", "please", "lonely", "scared", "worried",
                "anxious", "uncertain", "support", "comfort", "hold",
                "there for me", "listen", "understand me",
            ],
            "weight": 1.0,
        },
        "gratitude": {
            "terms": [
                "thank", "appreciate", "grateful", "thankful", "blessed",
                "means a lot", "so much", "kind", "generous", "touched",
            ],
            "weight": 1.0,
        },
        "connection": {
            "terms": [
                "together", "us", "we", "our", "share", "bond", "close",
                "connected", "relationship", "friendship", "partner",
            ],
            "weight": 0.9,
        },
        "vulnerability": {
            "terms": [
                "scared", "afraid", "nervous", "insecure", "doubt",
                "weak", "exposed", "honest", "admit", "confession",
                "hard to say", "opening up",
            ],
            "weight": 1.0,
        },
        "excitement": {
            "terms": [
                "can't wait", "excited", "thrilled", "eager", "pumped",
                "looking forward", "anticipating", "hyped",
            ],
            "weight": 1.0,
        },
        "frustration": {
            "terms": [
                "annoyed", "irritated", "frustrated", "angry", "mad",
                "ugh", "argh", "hate", "stupid", "ridiculous",
            ],
            "weight": 1.0,
        },
        "curiosity": {
            "terms": [
                "curious", "wonder", "what if", "how", "why", "explain",
                "tell me", "interested", "fascinated", "intrigued",
            ],
            "weight": 0.8,
        },
        "playfulness": {
            "terms": [
                "haha", "lol", "funny", "silly", "joke", "kidding",
                "playful", "tease", "goofy", "fun",
            ],
            "weight": 0.9,
        },
    }

    # Tones that are related and should cross-resonate
    RELATED_TONES: dict[str, list[str]] = {
        "grief": ["seeking_comfort", "vulnerability", "connection"],
        "struggle": ["seeking_comfort", "frustration", "vulnerability"],
        "joy": ["gratitude", "excitement", "playfulness"],
        "seeking_comfort": ["vulnerability", "connection", "grief"],
        "vulnerability": ["seeking_comfort", "connection", "trust"],
        "gratitude": ["joy", "connection"],
        "excitement": ["joy", "curiosity", "playfulness"],
    }

    def __init__(self):
        # Pre-compile patterns for efficiency
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for tone, data in self.EMOTION_LEXICON.items():
            patterns = []
            for term in data["terms"]:
                # Word boundary matching, case insensitive
                patterns.append(re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE))
            self._compiled_patterns[tone] = patterns

    def analyze(self, message: str) -> ToneResult:
        """
        Analyze the emotional tone of a message.

        Args:
            message: The text to analyze

        Returns:
            ToneResult with primary tone and all detected tones
        """
        if not message or not message.strip():
            return ToneResult(
                primary_tone="neutral",
                confidence=0.0,
                detected_tones={},
            )

        # Score each emotion category
        scores: dict[str, float] = {}

        for tone, patterns in self._compiled_patterns.items():
            weight = self.EMOTION_LEXICON[tone]["weight"]
            matches = sum(1 for p in patterns if p.search(message))

            if matches > 0:
                # Normalize by number of possible terms, apply weight
                raw_score = min(1.0, matches / (len(patterns) * 0.15))
                scores[tone] = raw_score * weight

        if not scores:
            return ToneResult(
                primary_tone="neutral",
                confidence=0.0,
                detected_tones={},
            )

        # Determine primary tone
        primary = max(scores, key=scores.get)
        confidence = scores[primary]

        return ToneResult(
            primary_tone=primary,
            confidence=confidence,
            detected_tones=scores,
        )

    def get_related_tones(self, tone: str) -> list[str]:
        """Get tones that are emotionally related to the given tone."""
        return self.RELATED_TONES.get(tone, [])

    def tones_align(
        self,
        tone1: str,
        tone2: str,
        include_related: bool = True,
    ) -> bool:
        """Check if two tones align (same or related)."""
        if tone1 == tone2:
            return True

        if include_related:
            related = self.get_related_tones(tone1)
            return tone2 in related

        return False
```

### Step 1.3: Create `resonance/entities.py`

```python
"""
Entity extraction for relational resonance.
"""

from __future__ import annotations

import re
from typing import Optional

from threadlight.resonance.types import EntityMention


class EntityExtractor:
    """
    Extract mentions of people and entities from messages.

    Prioritizes known entities from the user's relational capsules
    while also detecting patterns that suggest relationship references.
    """

    # Patterns for detecting relationship references
    RELATION_PATTERNS: list[tuple[re.Pattern, str, int]] = [
        # "my sister", "my friend", "my mom"
        (re.compile(r"\bmy\s+(\w+)\b", re.IGNORECASE), "possessive", 1),

        # "Sarah's birthday", "Mom's advice"
        (re.compile(r"\b(\w+)'s\b", re.IGNORECASE), "possessive_ref", 1),

        # "talking to Sarah", "with Mom"
        (re.compile(r"\bwith\s+([A-Z][a-z]+)\b"), "accompaniment", 1),
        (re.compile(r"\bto\s+([A-Z][a-z]+)\b"), "interaction", 1),

        # "about Sarah", "regarding Mom"
        (re.compile(r"\babout\s+([A-Z][a-z]+)\b"), "reference", 1),
        (re.compile(r"\bregarding\s+([A-Z][a-z]+)\b"), "reference", 1),

        # Standalone capitalized names (lower confidence)
        (re.compile(r"\b([A-Z][a-z]{2,})\b"), "name_mention", 1),
    ]

    # Common words that look like names but aren't
    FALSE_POSITIVES = {
        "the", "and", "but", "for", "not", "you", "all", "can", "had", "her",
        "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
        "its", "may", "new", "now", "old", "see", "two", "way", "who", "boy",
        "did", "man", "any", "let", "put", "say", "she", "too", "use", "the",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday", "january", "february", "march", "april", "june", "july",
        "august", "september", "october", "november", "december",
        "today", "tomorrow", "yesterday", "morning", "evening", "night",
        "just", "very", "really", "actually", "basically", "honestly",
    }

    # Relationship role words (when detected after "my")
    RELATIONSHIP_ROLES = {
        "mom", "mother", "dad", "father", "sister", "brother", "parent",
        "friend", "partner", "husband", "wife", "spouse", "boyfriend",
        "girlfriend", "son", "daughter", "grandmother", "grandfather",
        "grandma", "grandpa", "aunt", "uncle", "cousin", "niece", "nephew",
        "boss", "coworker", "colleague", "mentor", "teacher", "therapist",
        "doctor", "cat", "dog", "pet",
    }

    def extract(
        self,
        message: str,
        known_entities: Optional[list[str]] = None,
    ) -> list[EntityMention]:
        """
        Extract entity mentions from a message.

        Args:
            message: The message to analyze
            known_entities: List of entity names from RelationalThread capsules

        Returns:
            List of EntityMention with name, confidence, and relation type
        """
        known_entities = known_entities or []
        mentions: list[EntityMention] = []
        seen_names: set[str] = set()

        # First pass: check for known entities (highest confidence)
        message_lower = message.lower()
        for entity in known_entities:
            if entity.lower() in message_lower:
                mentions.append(EntityMention(
                    name=entity,
                    confidence=1.0,
                    relation_type="known",
                ))
                seen_names.add(entity.lower())

        # Second pass: pattern matching
        for pattern, rel_type, group_idx in self.RELATION_PATTERNS:
            for match in pattern.finditer(message):
                name = match.group(group_idx)
                name_lower = name.lower()

                # Skip if already seen or is a false positive
                if name_lower in seen_names:
                    continue
                if name_lower in self.FALSE_POSITIVES:
                    continue

                # Determine confidence based on pattern type
                confidence = self._get_pattern_confidence(rel_type, name_lower)

                if confidence > 0:
                    mentions.append(EntityMention(
                        name=name.title(),
                        confidence=confidence,
                        relation_type=rel_type,
                    ))
                    seen_names.add(name_lower)

        # Sort by confidence
        mentions.sort(key=lambda m: m.confidence, reverse=True)

        return mentions

    def _get_pattern_confidence(self, rel_type: str, name: str) -> float:
        """Determine confidence based on pattern type and name characteristics."""

        # "my sister" style - high confidence for role words
        if rel_type == "possessive":
            if name in self.RELATIONSHIP_ROLES:
                return 0.9
            return 0.7

        # "Sarah's" - moderate confidence
        if rel_type == "possessive_ref":
            if len(name) >= 3 and name[0].isupper():
                return 0.8
            return 0.4

        # "with Sarah", "about Sarah" - moderate confidence
        if rel_type in ("accompaniment", "interaction", "reference"):
            return 0.75

        # Standalone name - lower confidence, many false positives
        if rel_type == "name_mention":
            # Only include if it looks like a proper name
            if len(name) >= 3:
                return 0.5
            return 0.0

        return 0.5
```

---

## Phase 2: ResonanceEngine

### Step 2.1: Create `resonance/engine.py`

```python
"""
Core resonance scoring engine.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
import logging

from threadlight.resonance.types import (
    ToneResult,
    EntityMention,
    ResonanceScore,
    ResonanceContext,
)
from threadlight.resonance.tone import ToneAnalyzer

if TYPE_CHECKING:
    from threadlight.capsules.base import MemoryCapsule, CapsuleType
    from threadlight.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class ResonanceEngine:
    """
    Score memory capsules based on multi-dimensional resonance.

    Dimensions:
    - keyword: Traditional cue phrase matching
    - semantic: Embedding similarity (requires embedding provider)
    - emotional: Alignment of emotional tones
    - relational: Entity/relationship matching
    - temporal: Recency and access patterns
    """

    DEFAULT_WEIGHTS: dict[str, float] = {
        "keyword": 0.15,
        "semantic": 0.25,
        "emotional": 0.30,
        "relational": 0.20,
        "temporal": 0.10,
    }

    def __init__(
        self,
        embedding_provider: Optional['EmbeddingProvider'] = None,
        weights: Optional[dict[str, float]] = None,
    ):
        """
        Initialize the resonance engine.

        Args:
            embedding_provider: Optional provider for semantic similarity
            weights: Custom dimension weights (must sum to 1.0)
        """
        self.embedding_provider = embedding_provider
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._tone_analyzer = ToneAnalyzer()

        # Validate weights
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f"Resonance weights sum to {total}, normalizing")
            for k in self.weights:
                self.weights[k] /= total

    def score_capsule(
        self,
        capsule: 'MemoryCapsule',
        context: ResonanceContext,
    ) -> ResonanceScore:
        """
        Score a single capsule against the current context.

        Args:
            capsule: The memory capsule to score
            context: Current resonance context

        Returns:
            ResonanceScore with component breakdown
        """
        scores = ResonanceScore(capsule_id=capsule.id)

        # Compute each dimension
        scores.keyword = self._score_keyword(capsule, context.message)
        scores.emotional = self._score_emotional(capsule, context.tone)
        scores.relational = self._score_relational(capsule, context.entities)
        scores.temporal = self._score_temporal(capsule, context)

        # Semantic scoring (optional, requires embeddings)
        effective_weights = self.weights.copy()
        if self.embedding_provider and capsule.embedding and context.message_embedding:
            scores.semantic = cosine_similarity(
                context.message_embedding,
                capsule.embedding,
            )
        else:
            # Redistribute semantic weight to other dimensions
            scores.semantic = 0.0
            semantic_weight = effective_weights.pop("semantic", 0)
            if semantic_weight > 0:
                # Boost emotional and keyword proportionally
                effective_weights["emotional"] += semantic_weight * 0.6
                effective_weights["keyword"] += semantic_weight * 0.4

        # Compute weighted total
        scores.total = sum(
            effective_weights.get(dim, 0) * getattr(scores, dim)
            for dim in ["keyword", "semantic", "emotional", "relational", "temporal"]
        )

        return scores

    def score_capsules(
        self,
        capsules: list['MemoryCapsule'],
        context: ResonanceContext,
    ) -> list[ResonanceScore]:
        """Score multiple capsules, returning sorted scores."""
        scores = [self.score_capsule(c, context) for c in capsules]
        scores.sort(key=lambda s: s.total, reverse=True)
        return scores

    def _score_keyword(self, capsule: 'MemoryCapsule', message: str) -> float:
        """Score based on cue phrase matching."""
        if not capsule.cue_phrases:
            return 0.0

        message_lower = message.lower()
        matches = sum(1 for cue in capsule.cue_phrases if cue.lower() in message_lower)

        if matches == 0:
            return 0.0

        # Scale: 1 match = 0.5, 2 matches = 0.7, 3+ = higher
        return min(1.0, 0.3 + (matches * 0.2))

    def _score_emotional(self, capsule: 'MemoryCapsule', tone: ToneResult) -> float:
        """Score emotional alignment between capsule and current tone."""
        from threadlight.capsules.base import CapsuleType

        capsule_tones = self._extract_capsule_tones(capsule)

        if not capsule_tones or not tone.detected_tones:
            return 0.0

        max_alignment = 0.0

        for capsule_tone in capsule_tones:
            # Direct tone match
            if capsule_tone in tone.detected_tones:
                max_alignment = max(max_alignment, tone.detected_tones[capsule_tone])

            # Related tone match (reduced weight)
            related = self._tone_analyzer.get_related_tones(capsule_tone)
            for related_tone in related:
                if related_tone in tone.detected_tones:
                    max_alignment = max(
                        max_alignment,
                        tone.detected_tones[related_tone] * 0.7
                    )

        return max_alignment

    def _extract_capsule_tones(self, capsule: 'MemoryCapsule') -> list[str]:
        """Extract emotional tones from a capsule's content."""
        from threadlight.capsules.base import CapsuleType

        tones = []

        if capsule.type == CapsuleType.WITNESS:
            feeling = capsule.content.get("feeling", "")
            if feeling:
                # Analyze the feeling text to extract tone
                feeling_tone = self._tone_analyzer.analyze(feeling)
                if feeling_tone.primary_tone != "neutral":
                    tones.append(feeling_tone.primary_tone)
                # Also add high-scoring secondary tones
                for t, score in feeling_tone.detected_tones.items():
                    if score > 0.3 and t not in tones:
                        tones.append(t)

        elif capsule.type == CapsuleType.RELATIONAL:
            tone_field = capsule.content.get("tone", "")
            if tone_field:
                # RelationalThread tone is descriptive ("warm, proud")
                # Map to our emotion categories
                tone_lower = tone_field.lower()
                if any(w in tone_lower for w in ["warm", "loving", "affectionate"]):
                    tones.append("connection")
                if any(w in tone_lower for w in ["proud", "happy", "joyful"]):
                    tones.append("joy")
                if any(w in tone_lower for w in ["playful", "fun", "silly"]):
                    tones.append("playfulness")
                if any(w in tone_lower for w in ["protective", "caring"]):
                    tones.append("seeking_comfort")
                if any(w in tone_lower for w in ["curious", "interested"]):
                    tones.append("curiosity")

        elif capsule.type == CapsuleType.RITUAL:
            valence = capsule.content.get("valence", "")
            if valence:
                # Map ritual valence to emotion categories
                valence_lower = valence.lower()
                if "comfort" in valence_lower:
                    tones.append("seeking_comfort")
                if "joy" in valence_lower or "celebrat" in valence_lower:
                    tones.append("joy")
                if "ground" in valence_lower or "calm" in valence_lower:
                    tones.append("reflection")
                if "play" in valence_lower:
                    tones.append("playfulness")

        return tones

    def _score_relational(
        self,
        capsule: 'MemoryCapsule',
        entities: list[EntityMention],
    ) -> float:
        """Score relational connection to mentioned entities."""
        from threadlight.capsules.base import CapsuleType

        if capsule.type != CapsuleType.RELATIONAL:
            return 0.0

        if not entities:
            return 0.0

        capsule_entity = capsule.content.get("entity", "").lower()
        if not capsule_entity:
            return 0.0

        max_score = 0.0

        for mention in entities:
            mention_lower = mention.name.lower()

            # Exact match
            if mention_lower == capsule_entity:
                max_score = max(max_score, 1.0 * mention.confidence)
                continue

            # Partial match (e.g., "Mom" matching "Mom (Sarah)")
            if mention_lower in capsule_entity or capsule_entity in mention_lower:
                max_score = max(max_score, 0.8 * mention.confidence)
                continue

            # Role match (e.g., "my sister" matching entity with role "sister")
            capsule_role = capsule.content.get("role", "").lower()
            if capsule_role and mention_lower == capsule_role:
                max_score = max(max_score, 0.9 * mention.confidence)

        return max_score

    def _score_temporal(
        self,
        capsule: 'MemoryCapsule',
        context: ResonanceContext,
    ) -> float:
        """Score based on temporal relevance."""
        score = 0.0

        # Recently accessed in this session gets a boost
        if capsule.id in context.recent_capsule_ids:
            # Position matters - more recent = higher boost
            try:
                position = context.recent_capsule_ids.index(capsule.id)
                recency = 1.0 - (position / len(context.recent_capsule_ids))
                score += 0.5 * recency
            except ValueError:
                pass

        # Presence score captures decay - higher presence = more "alive"
        score += capsule.presence_score * 0.3

        # Access frequency (capped to avoid over-boosting popular memories)
        access_factor = min(1.0, capsule.access_count / 20.0)
        score += access_factor * 0.2

        return min(1.0, score)
```

### Step 2.2: Create `resonance/__init__.py`

```python
"""
Resonance-based memory activation.

This module provides emotional and relational resonance scoring
for memory retrieval, replacing simple keyword matching with
multi-dimensional relevance scoring.
"""

from threadlight.resonance.types import (
    ToneResult,
    EntityMention,
    ResonanceScore,
    ResonanceContext,
)
from threadlight.resonance.tone import ToneAnalyzer
from threadlight.resonance.entities import EntityExtractor
from threadlight.resonance.engine import ResonanceEngine

__all__ = [
    "ToneResult",
    "EntityMention",
    "ResonanceScore",
    "ResonanceContext",
    "ToneAnalyzer",
    "EntityExtractor",
    "ResonanceEngine",
]
```

---

## Phase 3: Integration with MemoryOrchestrator

### Step 3.1: Modify `memory/orchestrator.py`

Add new imports and initialization:

```python
# Add to imports
from threadlight.resonance import (
    ToneAnalyzer,
    EntityExtractor,
    ResonanceEngine,
    ResonanceContext,
    ResonanceScore,
)
```

Update `__init__`:

```python
def __init__(
    self,
    storage: StorageBackend,
    # ... existing params ...
    # New resonance params
    enable_resonance: bool = True,
    embedding_provider: Optional[EmbeddingProvider] = None,
    resonance_weights: Optional[dict[str, float]] = None,
):
    # ... existing init ...

    # Initialize resonance components
    self._enable_resonance = enable_resonance
    if enable_resonance:
        self._tone_analyzer = ToneAnalyzer()
        self._entity_extractor = EntityExtractor()
        self._resonance_engine = ResonanceEngine(
            embedding_provider=embedding_provider,
            weights=resonance_weights,
        )
    else:
        self._tone_analyzer = None
        self._entity_extractor = None
        self._resonance_engine = None
```

Replace `recall_for_message`:

```python
def recall_for_message(
    self,
    message: str,
    include_rituals: bool = True,
    include_style: bool = True,
    limit: int = 5,
    return_scores: bool = False,
) -> list[MemoryCapsule] | tuple[list[MemoryCapsule], list[ResonanceScore]]:
    """
    Recall memories that resonate with the current message.

    Uses multi-dimensional resonance scoring when enabled,
    falling back to keyword matching otherwise.

    Args:
        message: The user message to find relevant memories for
        include_rituals: Whether to check for ritual triggers
        include_style: Whether to include style profiles
        limit: Maximum capsules to return
        return_scores: If True, also return ResonanceScore breakdown

    Returns:
        List of relevant capsules, optionally with scores
    """
    self.record_interaction()

    # Use legacy keyword matching if resonance disabled
    if not self._enable_resonance:
        return self._recall_for_message_legacy(
            message, include_rituals, include_style, limit
        )

    # Build resonance context
    context = self._build_resonance_context(message)

    # Get candidate capsules
    candidates = self._get_candidate_capsules(include_rituals, include_style)

    if not candidates:
        if return_scores:
            return [], []
        return []

    # Score all candidates
    scores = self._resonance_engine.score_capsules(candidates, context)

    # Match capsules to scores
    score_by_id = {s.capsule_id: s for s in scores}
    scored_pairs = [
        (c, score_by_id[c.id])
        for c in candidates
        if c.id in score_by_id
    ]

    # Sort by score and filter
    scored_pairs.sort(key=lambda x: x[1].total, reverse=True)
    threshold = 0.1
    filtered = [(c, s) for c, s in scored_pairs if s.total >= threshold]

    # Take top results
    results = filtered[:limit]

    # Touch accessed capsules
    for capsule, score in results:
        capsule.touch()
        self.storage.update_capsule(capsule)
        if self._current_session:
            self._current_session.record_access(capsule.id)

    if return_scores:
        return [c for c, s in results], [s for c, s in results]
    return [c for c, s in results]

def _build_resonance_context(self, message: str) -> ResonanceContext:
    """Build the resonance context for scoring."""

    # Analyze tone
    tone = self._tone_analyzer.analyze(message)

    # Get known entities from relational capsules
    relational_capsules = self.list(type=CapsuleType.RELATIONAL, limit=100)
    known_entities = [c.content.get("entity", "") for c in relational_capsules]

    # Extract entity mentions
    entities = self._entity_extractor.extract(message, known_entities)

    # Get message embedding if available
    message_embedding = None
    if self._resonance_engine.embedding_provider:
        try:
            message_embedding = self._resonance_engine.embedding_provider.embed(message)
        except Exception as e:
            logger.debug(f"Failed to generate message embedding: {e}")

    # Get recent session context
    recent_ids = []
    if self._current_session:
        recent_ids = self._current_session.capsules_accessed[-10:]

    return ResonanceContext(
        message=message,
        tone=tone,
        entities=entities,
        message_embedding=message_embedding,
        recent_capsule_ids=recent_ids,
    )

def _recall_for_message_legacy(
    self,
    message: str,
    include_rituals: bool,
    include_style: bool,
    limit: int,
) -> list[MemoryCapsule]:
    """Legacy keyword-based recall (fallback when resonance disabled)."""
    # ... move existing recall_for_message code here ...
```

---

## Phase 4: Configuration

### Step 4.1: Update `config.py`

Add resonance configuration:

```python
@dataclass
class ResonanceConfig:
    """Configuration for resonance-based memory retrieval."""

    # Enable resonance (vs legacy keyword-only)
    enabled: bool = True

    # Dimension weights (should sum to 1.0)
    weights: dict[str, float] = field(default_factory=lambda: {
        "keyword": 0.15,
        "semantic": 0.25,
        "emotional": 0.30,
        "relational": 0.20,
        "temporal": 0.10,
    })

    # Minimum score threshold for inclusion
    threshold: float = 0.1

    # Maximum candidates to score
    max_candidates: int = 500

    # Use embeddings for semantic scoring
    use_embeddings: bool = True


@dataclass
class MemoryConfig:
    # ... existing fields ...

    # Add resonance config
    resonance: ResonanceConfig = field(default_factory=ResonanceConfig)
```

---

## Phase 5: Testing

### Step 5.1: Create `tests/test_resonance.py`

```python
"""Tests for resonance-based memory retrieval."""

import pytest
from threadlight.resonance import (
    ToneAnalyzer,
    EntityExtractor,
    ResonanceEngine,
    ResonanceContext,
    ToneResult,
)
from threadlight.capsules.witness import WitnessMoment
from threadlight.capsules.relational import RelationalThread


class TestToneAnalyzer:
    """Tests for emotional tone detection."""

    def setup_method(self):
        self.analyzer = ToneAnalyzer()

    def test_detects_struggle(self):
        result = self.analyzer.analyze("I'm really struggling with this")
        assert result.primary_tone == "struggle"
        assert result.confidence > 0.5

    def test_detects_joy(self):
        result = self.analyzer.analyze("I'm so excited and happy about this!")
        assert result.primary_tone in ("joy", "excitement")
        assert result.confidence > 0.5

    def test_detects_seeking_comfort(self):
        result = self.analyzer.analyze("I feel so lonely and need someone to listen")
        assert "seeking_comfort" in result.detected_tones

    def test_neutral_message(self):
        result = self.analyzer.analyze("The meeting is at 3pm")
        assert result.primary_tone == "neutral"
        assert result.confidence == 0.0

    def test_empty_message(self):
        result = self.analyzer.analyze("")
        assert result.primary_tone == "neutral"


class TestEntityExtractor:
    """Tests for entity/relationship extraction."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_extracts_known_entities(self):
        mentions = self.extractor.extract(
            "I was talking to Sarah yesterday",
            known_entities=["Sarah", "Mom"]
        )
        assert len(mentions) >= 1
        assert mentions[0].name == "Sarah"
        assert mentions[0].confidence == 1.0

    def test_extracts_possessive_relationships(self):
        mentions = self.extractor.extract("my sister called today")
        assert len(mentions) >= 1
        assert any(m.name.lower() == "sister" for m in mentions)

    def test_extracts_named_references(self):
        mentions = self.extractor.extract("I had coffee with David")
        assert len(mentions) >= 1
        assert any(m.name == "David" for m in mentions)

    def test_ignores_false_positives(self):
        mentions = self.extractor.extract("The Monday meeting was good")
        # "Monday" should be filtered out
        assert not any(m.name == "Monday" for m in mentions)


class TestResonanceEngine:
    """Tests for resonance scoring."""

    def setup_method(self):
        self.engine = ResonanceEngine()
        self.analyzer = ToneAnalyzer()

    def test_emotional_resonance_witness(self):
        """Witness moments should resonate when similar feelings arise."""
        capsule = WitnessMoment(
            moment="When they asked about my hopes",
            feeling="seen, validated, understood",
            consent_confirmed=True,
        )

        # Message with emotional resonance but no keyword overlap
        context = ResonanceContext(
            message="I feel like nobody really gets what I'm going through",
            tone=self.analyzer.analyze("I feel like nobody really gets what I'm going through"),
            entities=[],
        )

        score = self.engine.score_capsule(capsule, context)

        # Should have meaningful emotional score
        assert score.emotional > 0.0
        assert score.total > 0.1

    def test_relational_resonance(self):
        """Mentioning a person should surface their relational thread."""
        capsule = RelationalThread(
            entity="Sarah",
            tone="warm, proud",
            summary="My sister who taught me to code",
            consent_confirmed=True,
        )

        from threadlight.resonance.types import EntityMention

        context = ResonanceContext(
            message="I was talking to my sister yesterday",
            tone=ToneResult(primary_tone="neutral", confidence=0, detected_tones={}),
            entities=[EntityMention(name="sister", confidence=0.9, relation_type="possessive")],
        )

        score = self.engine.score_capsule(capsule, context)

        # Should have high relational score
        assert score.relational > 0.5
        assert score.total > 0.2

    def test_keyword_still_works(self):
        """Traditional keyword matching should still contribute."""
        capsule = RelationalThread(
            entity="Sarah",
            tone="warm",
            summary="My friend",
            cue_phrases=["sarah", "friend"],
            consent_confirmed=True,
        )

        context = ResonanceContext(
            message="Sarah and I went for coffee",
            tone=ToneResult(primary_tone="neutral", confidence=0, detected_tones={}),
            entities=[],  # No entity extraction for this test
        )

        score = self.engine.score_capsule(capsule, context)

        # Keyword should match
        assert score.keyword > 0.0

    def test_weights_sum_to_one(self):
        """Weight normalization should work correctly."""
        engine = ResonanceEngine(weights={
            "keyword": 0.5,
            "semantic": 0.5,
            "emotional": 0.5,
            "relational": 0.5,
            "temporal": 0.5,
        })

        total = sum(engine.weights.values())
        assert abs(total - 1.0) < 0.01
```

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Core Infrastructure | `resonance/` module with types, ToneAnalyzer, EntityExtractor, ResonanceEngine |
| 1 | Integration | Updated `MemoryOrchestrator.recall_for_message()` |
| 2 | Testing | Unit tests, integration tests, benchmark tests |
| 2 | Soft Memory | Resonance-aware soft memory recall |
| 3 | Configuration | Config options, documentation, tuning guide |

---

## Rollout Strategy

### Flag-Based Rollout

```python
# In config.py
resonance:
  enabled: true  # Set to false to use legacy behavior
```

### Comparison Testing

```python
# For A/B testing resonance effectiveness
def recall_for_message_compare(self, message: str, ...):
    """Compare resonance vs legacy recall for debugging."""
    legacy_results = self._recall_for_message_legacy(message, ...)
    resonance_results, scores = self.recall_for_message(message, ..., return_scores=True)

    return {
        "legacy": [c.id for c in legacy_results],
        "resonance": [(c.id, s.to_dict()) for c, s in zip(resonance_results, scores)],
    }
```

---

## Success Metrics

1. **Emotional Recall Accuracy**: Witness moments surface when similar feelings arise
2. **Relational Recall Accuracy**: Mentioning a person surfaces their thread
3. **Latency**: Total recall time < 100ms for typical workload
4. **User Satisfaction**: Subjective quality of memory surfacing in conversations

---

## Future Work

After MVP:
- Embedding-based tone analysis (Option B in architecture)
- Conversation-level emotional arc tracking
- Cross-capsule resonance (capsules that resonate with each other)
- Learned weight tuning based on user engagement
