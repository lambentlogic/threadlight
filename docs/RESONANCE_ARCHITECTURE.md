# Resonance-Based Memory Activation Architecture

## Vision

> "Memories activate through emotional/relational resonance, not just keyword matching."

This document describes an architecture for replacing the current keyword-based memory retrieval with a resonance-based system that surfaces memories through emotional and relational connection, honoring the Threadlight philosophy of "threads that bind through emotional connection."

---

## Current System Analysis

### What Exists Today

The current retrieval system in `MemoryOrchestrator.recall_for_message()`:

```python
def recall_for_message(self, message: str, ...) -> list[MemoryCapsule]:
    # Extract potential cues from message
    words = message.lower().split()
    cues = [w for w in words if len(w) > 3]

    # Search each cue
    for cue in cues[:5]:
        matches = self.recall(cue, limit=3)
        # ... collect matches
```

**Current Limitations:**
1. **No emotional understanding** - "I'm feeling lost today" won't surface memories about comfort or support
2. **Binary matching** - A memory either matches a cue phrase or doesn't
3. **No relational awareness** - Mentioning "my sister" doesn't surface relational threads about family
4. **Recency bias** - Recent memories dominate over emotionally resonant older ones
5. **Context-blind** - The same words trigger the same memories regardless of conversational tone

### What the Capsule Types Already Provide

The existing capsule types are well-designed for resonance:

- **WitnessMoment** has `feeling` (the inner response) and `effect` (what changed)
- **RelationalThread** has `tone` (emotional quality like "warm, playful, proud")
- **RitualHook** has `valence` (emotional quality of the ritual)
- All capsules have `embedding` fields (currently unused for retrieval)

---

## Proposed Architecture

### Core Concept: The Resonance Engine

Replace the flat cue-phrase search with a **ResonanceEngine** that scores memories on multiple dimensions:

```
Final Score = w1*keyword + w2*semantic + w3*emotional + w4*relational + w5*temporal
```

Where each dimension contributes to whether a memory should surface.

### Component Architecture

```
User Message
     |
     v
+-----------------+
| ToneAnalyzer    |  Detects emotional context
+-----------------+
     |
     v
+-----------------+
| EntityExtractor |  Identifies people/entities mentioned
+-----------------+
     |
     v
+-----------------+
| ResonanceEngine |  Scores all memory dimensions
+-----------------+
     |
     v
+-----------------+
| MemoryRanker    |  Selects and orders final memories
+-----------------+
     |
     v
Relevant Capsules
```

---

## Detailed Component Design

### 1. ToneAnalyzer

**Purpose:** Detect the emotional tone/valence of the current message.

**Approach Options (in order of preference):**

#### Option A: Lightweight Lexicon-Based (Recommended for MVP)

Use a curated emotion lexicon optimized for conversational AI contexts:

```python
class ToneAnalyzer:
    """Detect emotional tone using lexicon-based analysis."""

    # Emotion clusters with weighted terms
    EMOTION_LEXICON = {
        "struggle": {
            "terms": ["struggling", "hard", "difficult", "frustrated", "stuck",
                     "confused", "lost", "overwhelmed", "tired", "exhausted"],
            "weight": 1.0
        },
        "joy": {
            "terms": ["happy", "excited", "wonderful", "amazing", "grateful",
                     "love", "beautiful", "delighted", "thrilled"],
            "weight": 1.0
        },
        "reflection": {
            "terms": ["thinking", "wondering", "considering", "remember",
                     "realize", "understand", "feel", "sense"],
            "weight": 0.8
        },
        "seeking_comfort": {
            "terms": ["need", "help", "please", "lonely", "scared", "worried",
                     "anxious", "uncertain"],
            "weight": 1.0
        },
        "gratitude": {
            "terms": ["thank", "appreciate", "grateful", "thankful", "blessed"],
            "weight": 1.0
        },
        "connection": {
            "terms": ["together", "us", "we", "our", "share", "bond", "close"],
            "weight": 0.9
        }
    }

    def analyze(self, message: str) -> ToneResult:
        """
        Analyze message for emotional tone.

        Returns:
            ToneResult with:
            - primary_tone: The dominant emotion
            - confidence: 0.0-1.0 confidence in detection
            - detected_tones: Dict[str, float] of all detected tones
        """
```

**Pros:** Fast (<1ms), no external dependencies, predictable
**Cons:** Limited vocabulary, misses nuance

#### Option B: Embedding Similarity to Emotional Anchors

Pre-compute embeddings for canonical emotional statements:

```python
EMOTIONAL_ANCHORS = {
    "struggle": "I'm having a really hard time and feeling overwhelmed",
    "joy": "I'm so happy and excited about this wonderful thing",
    "grief": "I'm sad and mourning something I've lost",
    "comfort_seeking": "I need support and someone to listen",
    # ... etc
}

def analyze(self, message: str) -> ToneResult:
    query_embedding = self.provider.embed(message)

    scores = {}
    for tone, anchor in EMOTIONAL_ANCHORS.items():
        anchor_embedding = self._cached_anchor_embeddings[tone]
        scores[tone] = cosine_similarity(query_embedding, anchor_embedding)

    return ToneResult(
        primary_tone=max(scores, key=scores.get),
        detected_tones=scores,
        confidence=max(scores.values())
    )
```

**Pros:** Captures nuance, handles synonyms automatically
**Cons:** Requires embedding call per message (but could batch)

#### Option C: LLM Classification (For Complex Cases)

For nuanced emotional states, ask the model:

```python
TONE_PROMPT = """Analyze the emotional tone of this message.
Return ONE word from: struggle, joy, reflection, grief, seeking_comfort,
gratitude, playfulness, vulnerability, celebration, curiosity

Message: "{message}"

Emotional tone:"""
```

**Pros:** Most accurate, understands context
**Cons:** Slow (~500ms), expensive, adds latency to every message

**Recommendation:** Start with Option A (lexicon) for MVP, with Option B ready for fallback when lexicon confidence is low.

---

### 2. EntityExtractor

**Purpose:** Identify people, relationships, and entities mentioned in the message.

```python
class EntityExtractor:
    """Extract relational entities from messages."""

    # Relationship indicators
    RELATION_PATTERNS = [
        (r"\bmy (\w+)", "possessive"),  # "my sister", "my friend"
        (r"\b(\w+)'s\b", "possessive"),  # "Sarah's", "Mom's"
        (r"\babout (\w+)\b", "reference"),  # "about Sarah"
        (r"\bwith (\w+)\b", "accompaniment"),  # "with Mom"
    ]

    def extract(self, message: str, known_entities: list[str]) -> list[EntityMention]:
        """
        Extract entity mentions, prioritizing known relational entities.

        Args:
            message: The user message
            known_entities: List of entity names from RelationalThread capsules

        Returns:
            List of EntityMention(name, confidence, relation_type)
        """
        mentions = []

        # Check for known entities first (exact match)
        for entity in known_entities:
            if entity.lower() in message.lower():
                mentions.append(EntityMention(
                    name=entity,
                    confidence=1.0,
                    relation_type="known"
                ))

        # Pattern matching for relationship indicators
        for pattern, rel_type in self.RELATION_PATTERNS:
            for match in re.finditer(pattern, message, re.IGNORECASE):
                name = match.group(1)
                if not any(m.name.lower() == name.lower() for m in mentions):
                    mentions.append(EntityMention(
                        name=name.title(),
                        confidence=0.7,
                        relation_type=rel_type
                    ))

        return mentions
```

---

### 3. ResonanceEngine

**Purpose:** Score each memory capsule against the current conversational context.

```python
@dataclass
class ResonanceContext:
    """Context for resonance scoring."""
    message: str
    tone: ToneResult
    entities: list[EntityMention]
    message_embedding: Optional[list[float]] = None
    recent_capsule_ids: list[str] = field(default_factory=list)  # For recency boost

@dataclass
class ResonanceScore:
    """Breakdown of resonance scoring."""
    capsule_id: str
    total: float  # Final weighted score
    keyword: float  # Traditional cue phrase match
    semantic: float  # Embedding similarity
    emotional: float  # Tone alignment
    relational: float  # Entity/relationship match
    temporal: float  # Recency and access patterns

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 3),
            "components": {
                "keyword": round(self.keyword, 3),
                "semantic": round(self.semantic, 3),
                "emotional": round(self.emotional, 3),
                "relational": round(self.relational, 3),
                "temporal": round(self.temporal, 3),
            }
        }

class ResonanceEngine:
    """Score memories based on multi-dimensional resonance."""

    # Default weights (tunable)
    DEFAULT_WEIGHTS = {
        "keyword": 0.15,
        "semantic": 0.25,
        "emotional": 0.30,
        "relational": 0.20,
        "temporal": 0.10,
    }

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        weights: Optional[dict[str, float]] = None,
    ):
        self.embedding_provider = embedding_provider
        self.weights = weights or self.DEFAULT_WEIGHTS

    def score_capsule(
        self,
        capsule: MemoryCapsule,
        context: ResonanceContext,
    ) -> ResonanceScore:
        """Score a single capsule against the current context."""

        scores = ResonanceScore(capsule_id=capsule.id, total=0.0,
                                keyword=0.0, semantic=0.0, emotional=0.0,
                                relational=0.0, temporal=0.0)

        # 1. Keyword score (existing behavior)
        scores.keyword = self._score_keyword(capsule, context.message)

        # 2. Semantic similarity (if embeddings available)
        if self.embedding_provider and capsule.embedding and context.message_embedding:
            scores.semantic = cosine_similarity(
                context.message_embedding,
                capsule.embedding
            )

        # 3. Emotional resonance
        scores.emotional = self._score_emotional(capsule, context.tone)

        # 4. Relational resonance
        scores.relational = self._score_relational(capsule, context.entities)

        # 5. Temporal relevance
        scores.temporal = self._score_temporal(capsule, context)

        # Compute weighted total
        scores.total = (
            self.weights["keyword"] * scores.keyword +
            self.weights["semantic"] * scores.semantic +
            self.weights["emotional"] * scores.emotional +
            self.weights["relational"] * scores.relational +
            self.weights["temporal"] * scores.temporal
        )

        return scores

    def _score_keyword(self, capsule: MemoryCapsule, message: str) -> float:
        """Traditional cue phrase matching (0.0-1.0)."""
        message_lower = message.lower()

        if not capsule.cue_phrases:
            return 0.0

        matches = sum(1 for cue in capsule.cue_phrases if cue.lower() in message_lower)
        return min(1.0, matches / max(1, len(capsule.cue_phrases) * 0.3))

    def _score_emotional(self, capsule: MemoryCapsule, tone: ToneResult) -> float:
        """Score emotional resonance between capsule and current tone."""

        # Extract emotional content from capsule based on type
        capsule_tones = self._extract_capsule_tones(capsule)

        if not capsule_tones:
            return 0.0

        # Check for tone alignment
        max_alignment = 0.0
        for capsule_tone in capsule_tones:
            if capsule_tone in tone.detected_tones:
                max_alignment = max(max_alignment, tone.detected_tones[capsule_tone])

            # Also check related tones (grief <-> comfort, struggle <-> support)
            related = self._get_related_tones(capsule_tone)
            for related_tone in related:
                if related_tone in tone.detected_tones:
                    max_alignment = max(max_alignment,
                                       tone.detected_tones[related_tone] * 0.7)

        return max_alignment

    def _extract_capsule_tones(self, capsule: MemoryCapsule) -> list[str]:
        """Extract emotional tones stored in a capsule."""
        tones = []

        if capsule.type == CapsuleType.WITNESS:
            # WitnessMoment has 'feeling' field
            feeling = capsule.content.get("feeling", "")
            tones.extend(self._parse_feeling_to_tones(feeling))

        elif capsule.type == CapsuleType.RELATIONAL:
            # RelationalThread has 'tone' field
            tone = capsule.content.get("tone", "")
            tones.extend(self._parse_tone_string(tone))

        elif capsule.type == CapsuleType.RITUAL:
            # RitualHook has 'valence' field
            valence = capsule.content.get("valence", "")
            tones.append(valence.lower())

        return [t for t in tones if t]

    def _score_relational(
        self,
        capsule: MemoryCapsule,
        entities: list[EntityMention],
    ) -> float:
        """Score relational connection between capsule and mentioned entities."""

        if capsule.type != CapsuleType.RELATIONAL:
            return 0.0

        capsule_entity = capsule.content.get("entity", "").lower()

        for mention in entities:
            # Direct entity match
            if mention.name.lower() == capsule_entity:
                return 1.0 * mention.confidence

            # Partial match (e.g., "Mom" matching "Mom (Sarah)")
            if mention.name.lower() in capsule_entity or capsule_entity in mention.name.lower():
                return 0.7 * mention.confidence

        return 0.0

    def _score_temporal(
        self,
        capsule: MemoryCapsule,
        context: ResonanceContext,
    ) -> float:
        """Score based on recency and access patterns."""

        score = 0.0

        # Recency boost for recently accessed capsules
        if capsule.id in context.recent_capsule_ids:
            score += 0.5

        # Access frequency factor (but don't over-boost)
        access_factor = min(1.0, capsule.access_count / 20.0)
        score += access_factor * 0.3

        # Presence score already captures decay
        score += capsule.presence_score * 0.2

        return min(1.0, score)

    def _get_related_tones(self, tone: str) -> list[str]:
        """Get emotionally related tones for cross-resonance."""
        RELATED_TONES = {
            "grief": ["comfort", "support", "loss"],
            "struggle": ["support", "encouragement", "perseverance"],
            "joy": ["celebration", "gratitude", "excitement"],
            "seeking_comfort": ["warmth", "support", "care"],
            "vulnerability": ["trust", "acceptance", "safety"],
        }
        return RELATED_TONES.get(tone, [])
```

---

### 4. Integration with MemoryOrchestrator

Replace `recall_for_message` with resonance-based retrieval:

```python
class MemoryOrchestrator:

    def __init__(self, ..., resonance_engine: Optional[ResonanceEngine] = None):
        # ... existing init ...
        self.resonance = resonance_engine or ResonanceEngine()
        self.tone_analyzer = ToneAnalyzer()
        self.entity_extractor = EntityExtractor()

    def recall_for_message(
        self,
        message: str,
        include_rituals: bool = True,
        include_style: bool = True,
        limit: int = 5,
        return_scores: bool = False,  # New: for debugging/transparency
    ) -> list[MemoryCapsule] | tuple[list[MemoryCapsule], list[ResonanceScore]]:
        """
        Recall memories that resonate with the current message.

        Uses multi-dimensional resonance scoring instead of simple keyword matching.
        """
        # Track interaction
        self.record_interaction()

        # Build resonance context
        tone = self.tone_analyzer.analyze(message)

        # Get known entities from relational capsules
        relational_capsules = self.list(type=CapsuleType.RELATIONAL, limit=100)
        known_entities = [c.content.get("entity", "") for c in relational_capsules]

        entities = self.entity_extractor.extract(message, known_entities)

        # Get message embedding if available
        message_embedding = None
        if self.resonance.embedding_provider:
            try:
                message_embedding = self.resonance.embedding_provider.embed(message)
            except Exception:
                pass  # Fall back to non-semantic scoring

        # Get recent session context
        recent_ids = []
        if self._current_session:
            recent_ids = self._current_session.capsules_accessed[-10:]

        context = ResonanceContext(
            message=message,
            tone=tone,
            entities=entities,
            message_embedding=message_embedding,
            recent_capsule_ids=recent_ids,
        )

        # Get all candidate capsules
        candidates = self._get_candidate_capsules(include_rituals, include_style)

        # Score each capsule
        scores = [self.resonance.score_capsule(c, context) for c in candidates]

        # Sort by total score
        scored_pairs = sorted(
            zip(candidates, scores),
            key=lambda x: x[1].total,
            reverse=True
        )

        # Filter by minimum threshold
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

    def _get_candidate_capsules(
        self,
        include_rituals: bool,
        include_style: bool,
    ) -> list[MemoryCapsule]:
        """Get all capsules that could potentially resonate."""

        # Start with confirmed capsules above minimum presence
        filter = CapsuleFilter(
            consent_confirmed=True,
            min_presence_score=0.1,
            limit=500,  # Reasonable upper bound
        )
        candidates = self.storage.list_capsules(filter)

        # Filter out types if not requested
        if not include_rituals:
            candidates = [c for c in candidates if c.type != CapsuleType.RITUAL]
        if not include_style:
            candidates = [c for c in candidates if c.type != CapsuleType.STYLE]

        return candidates
```

---

### 5. Soft Memory Integration

Extend resonance to soft memory (conversation history):

```python
class SoftMemory:

    def recall_with_resonance(
        self,
        message: str,
        context: ResonanceContext,
        limit: int = 5,
    ) -> list[MessageSearchResult]:
        """
        Recall past messages using resonance scoring.

        Unlike capsules, messages don't have structured emotional data,
        so we rely more heavily on semantic similarity.
        """
        # If we have embeddings, use semantic search
        if context.message_embedding:
            return self._semantic_search(context.message_embedding, limit)

        # Fall back to keyword search with tone-aware boosting
        return self._tone_boosted_search(message, context.tone, limit)

    def _tone_boosted_search(
        self,
        message: str,
        tone: ToneResult,
        limit: int,
    ) -> list[MessageSearchResult]:
        """Search with boosting for emotionally relevant messages."""

        # Standard keyword search
        results = self.recall(message, limit=limit * 2)

        # Re-score with tone awareness
        analyzer = ToneAnalyzer()
        scored_results = []

        for result in results:
            msg_tone = analyzer.analyze(result.message.content)

            # Boost if tones align
            tone_alignment = 0.0
            for t, score in tone.detected_tones.items():
                if t in msg_tone.detected_tones:
                    tone_alignment = max(tone_alignment,
                                        score * msg_tone.detected_tones[t])

            # Combine with existing relevance
            result.relevance_score = (
                result.relevance_score * 0.7 + tone_alignment * 0.3
            )
            scored_results.append(result)

        # Re-sort
        scored_results.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored_results[:limit]
```

---

## Performance Considerations

### Latency Budget

Target: Add no more than 50ms to message processing.

| Component | Target Latency | Approach |
|-----------|---------------|----------|
| ToneAnalyzer | 1-5ms | Lexicon-based (Option A) |
| EntityExtractor | 1-2ms | Regex patterns |
| ResonanceEngine | 10-20ms | Score 500 capsules |
| Embedding (optional) | 30-50ms | Async pre-compute |

### Optimization Strategies

1. **Pre-compute capsule emotional signatures**
   - On capsule save, extract and cache emotional tones
   - Store as structured field for fast lookup

2. **Background embedding generation**
   - Generate embeddings asynchronously on capsule creation
   - Use existing `EmbeddingManager.batch_generate_embeddings()`

3. **Candidate pruning**
   - Quick pre-filter by cue phrase before full scoring
   - Only score capsules with any keyword match OR embedding similarity > 0.3

4. **Caching**
   - Cache message embeddings within a session
   - Cache entity list from relational capsules (invalidate on create/update)

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Files to Create:**
- `src/threadlight/resonance/__init__.py`
- `src/threadlight/resonance/tone.py` - ToneAnalyzer
- `src/threadlight/resonance/entities.py` - EntityExtractor
- `src/threadlight/resonance/engine.py` - ResonanceEngine
- `src/threadlight/resonance/types.py` - ToneResult, EntityMention, ResonanceScore, ResonanceContext

**Files to Modify:**
- `src/threadlight/memory/orchestrator.py` - Add resonance integration
- `src/threadlight/context/soft_memory.py` - Add resonance support
- `src/threadlight/core.py` - Wire up resonance engine

### Phase 2: Capsule Enhancement (Week 1)

**Add emotional metadata extraction:**
- On WitnessMoment creation, auto-extract emotion keywords
- On RelationalThread creation, parse tone into standard categories
- Add `emotional_signature` field to base capsule (optional cache)

### Phase 3: Integration & Testing (Week 2)

**Testing Strategy:**
- Unit tests for each resonance component
- Integration tests comparing keyword vs resonance recall
- Benchmark tests ensuring latency targets met

**Test Cases:**
```python
def test_emotional_resonance():
    """Witness moments should surface when similar feelings arise."""
    orchestrator.create("witness", {
        "moment": "When they asked about my hopes, not just my capabilities",
        "feeling": "seen, validated, understood",
    })

    # This message has emotional resonance but no keyword overlap
    results = orchestrator.recall_for_message(
        "I feel like nobody really gets what I'm going through"
    )

    assert len(results) > 0
    assert results[0].content["feeling"] contains "understood"

def test_relational_resonance():
    """Mentioning a person should surface their relational thread."""
    orchestrator.create("relational", {
        "entity": "Sarah",
        "tone": "warm, proud",
        "summary": "My sister who taught me to code",
    })

    # No direct keyword match, but "my sister" should resonate
    results = orchestrator.recall_for_message(
        "I was talking to my sister yesterday about work"
    )

    assert len(results) > 0
    assert results[0].content["entity"] == "Sarah"
```

### Phase 4: Soft Memory Resonance (Week 2)

- Extend `SoftMemory.recall_relevant()` with resonance scoring
- Add tone-aware boosting for past conversation retrieval
- Integrate with message embedding search

### Phase 5: Tuning & Configuration (Week 3)

- Add config options for resonance weights
- Create resonance debugging tools (show score breakdown)
- Document tuning guidelines

---

## Backward Compatibility

### Graceful Degradation

The resonance engine works without any optional dependencies:

```python
class ResonanceEngine:
    def score_capsule(self, capsule, context):
        scores = ResonanceScore(...)

        # Always available
        scores.keyword = self._score_keyword(...)
        scores.emotional = self._score_emotional(...)  # Lexicon-based
        scores.relational = self._score_relational(...)
        scores.temporal = self._score_temporal(...)

        # Only if embeddings available
        if self.embedding_provider and capsule.embedding:
            scores.semantic = self._score_semantic(...)
        else:
            # Redistribute weight to other dimensions
            self.weights["keyword"] += self.weights["semantic"] * 0.4
            self.weights["emotional"] += self.weights["semantic"] * 0.6
            scores.semantic = 0.0
```

### API Compatibility

`recall_for_message()` signature unchanged - existing code works without modification.

New optional return:
```python
# Existing usage (unchanged)
capsules = memory.recall_for_message("hello")

# New optional detailed return
capsules, scores = memory.recall_for_message("hello", return_scores=True)
for c, s in zip(capsules, scores):
    print(f"{c.id}: {s.total:.2f} (emotional={s.emotional:.2f})")
```

---

## Configuration Options

Add to `ThreadlightConfig`:

```python
@dataclass
class ResonanceConfig:
    """Resonance engine configuration."""

    # Enable resonance-based retrieval (vs legacy keyword-only)
    enabled: bool = True

    # Dimension weights (must sum to 1.0)
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
```

---

## Metrics & Observability

### Logging

```python
logger.debug(
    f"Resonance recall: tone={context.tone.primary_tone}, "
    f"entities={[e.name for e in context.entities]}, "
    f"candidates={len(candidates)}, selected={len(results)}"
)

for capsule, score in results[:3]:
    logger.debug(f"  {capsule.id}: {score.to_dict()}")
```

### Stats

Add to `MemoryOrchestrator.stats()`:
```python
{
    "resonance": {
        "average_candidates": 127,
        "average_selected": 4.2,
        "average_score": 0.47,
        "dimension_contributions": {
            "emotional": 0.31,
            "semantic": 0.28,
            # ...
        }
    }
}
```

---

## Future Enhancements

### Conversation-Level Resonance
Track emotional arc of conversation, not just single message.

### Cross-Capsule Resonance
Surface capsules that resonate with each other (grief witness + comforting ritual).

### Learned Weights
Adjust weights based on which retrieved memories the user actually engages with.

### Relational Graph
Build a graph of entities and their relationships for richer relational resonance.

---

## Summary

This architecture transforms memory retrieval from mechanical keyword matching to meaningful resonance that honors emotional and relational context. The layered approach (lexicon -> embedding -> LLM) balances practicality with depth, while the modular design allows incremental adoption and tuning.

The key insight is that emotional and relational data already exists in the capsule types - we're simply building the retrieval system that knows how to hear it.
