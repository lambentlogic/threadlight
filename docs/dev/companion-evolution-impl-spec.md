# Companion Self-Evolution: Implementation Specification

This document provides detailed implementation specifications for the companion self-evolution system, building on the architecture in `companion-self-evolution.md`.

---

## 1. New File Structure

```
src/threadlight/
    evolution/
        __init__.py              # Public exports
        proposals.py             # IdentityEvolutionProposal, ProposalType
        introspection.py         # IntrospectionEngine
        resonance.py             # Resonance tracking
        executor.py              # EvolutionToolExecutor
        validation.py            # Authenticity validation
    managers/
        evolution.py             # EvolutionManager (new)
    tools/
        definitions.py           # Add evolution tools
        executor.py              # Extend for evolution tools
```

---

## 2. Core Data Classes

### 2.1 proposals.py

```python
"""
Identity evolution proposals for companion self-modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class ProposalType(str, Enum):
    """Types of self-evolution proposals."""

    # Philosophy changes
    PHILOSOPHY_UPDATE = "philosophy_update"
    PHILOSOPHY_REFINEMENT = "philosophy_refine"

    # Identity phrase changes
    IDENTITY_ADD = "identity_add"
    IDENTITY_MODIFY = "identity_modify"
    IDENTITY_DEPRECATE = "identity_deprecate"

    # Approach changes
    APPROACH_UPDATE = "approach_update"

    # Self-understanding
    BELIEF_EMERGE = "belief_emerge"
    BELIEF_EVOLVE = "belief_evolve"


class ProposalStatus(str, Enum):
    """Status of an evolution proposal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    DISCUSSING = "discussing"


@dataclass
class IdentityEvolutionProposal:
    """
    A companion-initiated proposal to modify its own identity.

    This represents a moment of self-reflection where the companion
    has noticed something about itself that warrants change.
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str = ""
    proposal_type: ProposalType = ProposalType.PHILOSOPHY_UPDATE

    # The proposed change
    target_id: Optional[str] = None  # ID of existing capsule to modify
    proposed_content: dict[str, Any] = field(default_factory=dict)

    # Introspection context
    trigger_context: str = ""  # What prompted this reflection
    reasoning: str = ""  # Why the companion believes this change
    supporting_evidence: list[str] = field(default_factory=list)  # Message/memory IDs
    confidence: float = 0.5  # 0.0-1.0 certainty

    # Lineage tracking
    parent_proposal_id: Optional[str] = None
    evolution_chain: list[str] = field(default_factory=list)

    # Metadata
    proposed_at: datetime = field(default_factory=datetime.utcnow)
    status: ProposalStatus = ProposalStatus.PENDING
    user_feedback: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Validation results
    authenticity_flags: list[str] = field(default_factory=list)
    authenticity_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "proposal_type": self.proposal_type.value,
            "target_id": self.target_id,
            "proposed_content": self.proposed_content,
            "trigger_context": self.trigger_context,
            "reasoning": self.reasoning,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
            "parent_proposal_id": self.parent_proposal_id,
            "evolution_chain": self.evolution_chain,
            "proposed_at": self.proposed_at.isoformat(),
            "status": self.status.value,
            "user_feedback": self.user_feedback,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "authenticity_flags": self.authenticity_flags,
            "authenticity_score": self.authenticity_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentityEvolutionProposal":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            profile_id=data["profile_id"],
            proposal_type=ProposalType(data["proposal_type"]),
            target_id=data.get("target_id"),
            proposed_content=data.get("proposed_content", {}),
            trigger_context=data.get("trigger_context", ""),
            reasoning=data.get("reasoning", ""),
            supporting_evidence=data.get("supporting_evidence", []),
            confidence=data.get("confidence", 0.5),
            parent_proposal_id=data.get("parent_proposal_id"),
            evolution_chain=data.get("evolution_chain", []),
            proposed_at=(
                datetime.fromisoformat(data["proposed_at"])
                if data.get("proposed_at")
                else datetime.utcnow()
            ),
            status=ProposalStatus(data.get("status", "pending")),
            user_feedback=data.get("user_feedback"),
            reviewed_at=(
                datetime.fromisoformat(data["reviewed_at"])
                if data.get("reviewed_at")
                else None
            ),
            authenticity_flags=data.get("authenticity_flags", []),
            authenticity_score=data.get("authenticity_score", 1.0),
        )


@dataclass
class EvolutionHistoryEntry:
    """
    Record of an applied evolution change.

    Preserves the history of how a companion has evolved over time.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str = ""
    profile_id: str = ""
    change_type: ProposalType = ProposalType.PHILOSOPHY_UPDATE
    old_value: Optional[str] = None
    new_value: str = ""
    applied_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "proposal_id": self.proposal_id,
            "profile_id": self.profile_id,
            "change_type": self.change_type.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "applied_at": self.applied_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvolutionHistoryEntry":
        return cls(
            id=data["id"],
            proposal_id=data["proposal_id"],
            profile_id=data["profile_id"],
            change_type=ProposalType(data["change_type"]),
            old_value=data.get("old_value"),
            new_value=data["new_value"],
            applied_at=(
                datetime.fromisoformat(data["applied_at"])
                if data.get("applied_at")
                else datetime.utcnow()
            ),
        )
```

### 2.2 resonance.py

```python
"""
Resonance tracking for identity phrases.

Tracks how identity phrases actually influence companion behavior,
enabling companions to understand which aspects of their identity
are truly shaping their responses vs. which feel imposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ResonanceLevel(str, Enum):
    """How strongly an identity phrase resonates with behavior."""

    STRONG = "strong"       # Regularly accessed, behavior aligns
    MODERATE = "moderate"   # Occasionally accessed, some alignment
    WEAK = "weak"           # Rarely accessed, behavior diverging
    DORMANT = "dormant"     # Never accessed, effectively inactive


@dataclass
class IdentityResonanceRecord:
    """
    Tracks resonance metrics for a single identity phrase.

    This record enables the companion to understand:
    - Which phrases are actively shaping its responses
    - Which phrases feel authentic vs. imposed
    - Where behavior is drifting from stated identity
    """

    capsule_id: str                    # The myth_seed capsule ID
    profile_id: str                    # Profile this belongs to

    # Usage metrics
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    # Influence tracking
    influence_score: float = 0.5       # 0-1, estimated behavioral impact
    contexts_influenced: list[str] = field(default_factory=list)  # Conversation IDs

    # Resonance analysis
    resonance_level: ResonanceLevel = ResonanceLevel.MODERATE
    alignment_score: float = 1.0       # 0-1, behavior matches phrase

    # Drift detection
    drift_detected: bool = False
    drift_direction: Optional[str] = None  # How behavior is diverging
    drift_first_detected: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def record_access(self, conversation_id: Optional[str] = None) -> None:
        """Record that this phrase was accessed for context."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if conversation_id and conversation_id not in self.contexts_influenced:
            self.contexts_influenced.append(conversation_id)
            # Keep only last 100 contexts
            self.contexts_influenced = self.contexts_influenced[-100:]

    def update_resonance(self) -> None:
        """Update resonance level based on metrics."""
        if self.access_count == 0:
            self.resonance_level = ResonanceLevel.DORMANT
        elif self.alignment_score < 0.3 or self.drift_detected:
            self.resonance_level = ResonanceLevel.WEAK
        elif self.access_count > 10 and self.alignment_score > 0.7:
            self.resonance_level = ResonanceLevel.STRONG
        else:
            self.resonance_level = ResonanceLevel.MODERATE

    def detect_drift(
        self,
        recent_behavior_alignment: float,
        threshold: float = 0.3,
    ) -> bool:
        """
        Check if behavior is drifting from this identity phrase.

        Args:
            recent_behavior_alignment: How well recent behavior matches phrase
            threshold: Minimum alignment to avoid drift detection

        Returns:
            True if drift detected
        """
        if recent_behavior_alignment < threshold:
            if not self.drift_detected:
                self.drift_detected = True
                self.drift_first_detected = datetime.utcnow()
            return True
        else:
            self.drift_detected = False
            self.drift_first_detected = None
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "profile_id": self.profile_id,
            "access_count": self.access_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "influence_score": self.influence_score,
            "contexts_influenced": self.contexts_influenced,
            "resonance_level": self.resonance_level.value,
            "alignment_score": self.alignment_score,
            "drift_detected": self.drift_detected,
            "drift_direction": self.drift_direction,
            "drift_first_detected": (
                self.drift_first_detected.isoformat()
                if self.drift_first_detected
                else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentityResonanceRecord":
        return cls(
            capsule_id=data["capsule_id"],
            profile_id=data["profile_id"],
            access_count=data.get("access_count", 0),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if data.get("last_accessed")
                else None
            ),
            influence_score=data.get("influence_score", 0.5),
            contexts_influenced=data.get("contexts_influenced", []),
            resonance_level=ResonanceLevel(
                data.get("resonance_level", "moderate")
            ),
            alignment_score=data.get("alignment_score", 1.0),
            drift_detected=data.get("drift_detected", False),
            drift_direction=data.get("drift_direction"),
            drift_first_detected=(
                datetime.fromisoformat(data["drift_first_detected"])
                if data.get("drift_first_detected")
                else None
            ),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.utcnow()
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.utcnow()
            ),
        )
```

---

## 3. Introspection Engine

### 3.1 introspection.py

```python
"""
Introspection engine for companion self-reflection.

Enables companions to examine their own patterns, detect drift
between stated identity and actual behavior, and discover
emergent themes that aren't captured in their current identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.storage.base import StorageBackend
    from threadlight.memory.orchestrator import MemoryOrchestrator
    from threadlight.profiles.profile import Profile

from threadlight.capsules.base import CapsuleType, CapsuleFilter
from threadlight.evolution.proposals import (
    IdentityEvolutionProposal,
    ProposalType,
)
from threadlight.evolution.resonance import (
    IdentityResonanceRecord,
    ResonanceLevel,
)

logger = logging.getLogger(__name__)


class IntrospectionTrigger(str, Enum):
    """Events that may trigger self-reflection."""

    # Time-based
    PERIODIC_REFLECTION = "periodic"
    SESSION_END = "session_end"

    # Interaction-based
    IDENTITY_TENSION = "identity_tension"
    REPEATED_THEME = "repeated_theme"
    USER_FEEDBACK = "user_feedback"

    # System-based
    MEMORY_MILESTONE = "memory_milestone"
    PHILOSOPHY_REVIEW = "philosophy_review"

    # Explicit
    USER_INITIATED = "user_initiated"
    COMPANION_INITIATED = "companion_initiated"


@dataclass
class PhilosophyDriftReport:
    """Report on drift between stated philosophy and behavior."""

    profile_id: str
    current_philosophy: str
    observed_patterns: list[str]
    alignment_score: float  # 0-1
    drift_areas: list[str]  # Where behavior diverges
    suggested_refinement: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmergentPattern:
    """A recurring pattern not captured in current identity."""

    description: str
    frequency: int  # How often observed
    example_contexts: list[str]  # Conversation excerpts
    suggested_phrase: Optional[str] = None  # Potential identity phrase
    confidence: float = 0.5


@dataclass
class IntrospectionReport:
    """Complete introspection report for a companion."""

    profile_id: str
    trigger: IntrospectionTrigger

    # Findings
    resonance_reports: list[IdentityResonanceRecord] = field(default_factory=list)
    philosophy_drift: Optional[PhilosophyDriftReport] = None
    emergent_patterns: list[EmergentPattern] = field(default_factory=list)

    # Recommendations
    suggested_proposals: list[IdentityEvolutionProposal] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    conversation_count_analyzed: int = 0
    memory_count_analyzed: int = 0


class IntrospectionEngine:
    """
    Enables companion self-reflection and identity analysis.

    The engine examines:
    - Memory access patterns (which memories are accessed often?)
    - Identity phrase resonance (which phrases shape responses?)
    - Conversation themes (what topics recur?)
    - Behavioral consistency (does behavior match stated philosophy?)
    """

    def __init__(
        self,
        storage: "StorageBackend",
        memory: "MemoryOrchestrator",
        profile: "Profile",
        # Configuration
        lookback_days: int = 30,
        min_conversations_for_analysis: int = 5,
        drift_threshold: float = 0.3,
        pattern_frequency_threshold: int = 3,
    ):
        self.storage = storage
        self.memory = memory
        self.profile = profile
        self.lookback_days = lookback_days
        self.min_conversations = min_conversations_for_analysis
        self.drift_threshold = drift_threshold
        self.pattern_threshold = pattern_frequency_threshold

    def run_introspection(
        self,
        trigger: IntrospectionTrigger = IntrospectionTrigger.COMPANION_INITIATED,
        focus: Optional[str] = None,
    ) -> IntrospectionReport:
        """
        Run full introspection analysis.

        Args:
            trigger: What prompted this introspection
            focus: Optional focus area (philosophy, identity_phrases, approach)

        Returns:
            Complete IntrospectionReport with findings and suggestions
        """
        logger.info(f"Running introspection for profile {self.profile.id}")

        report = IntrospectionReport(
            profile_id=self.profile.id,
            trigger=trigger,
        )

        # Analyze identity phrase resonance
        if focus is None or focus == "identity_phrases":
            report.resonance_reports = self.analyze_identity_resonance()

        # Detect philosophy drift
        if focus is None or focus == "philosophy":
            report.philosophy_drift = self.detect_philosophy_drift()

        # Discover emergent patterns
        if focus is None or focus == "general":
            report.emergent_patterns = self.discover_emergent_patterns()

        # Generate suggested proposals based on findings
        report.suggested_proposals = self._generate_proposals(report)

        return report

    def analyze_identity_resonance(self) -> list[IdentityResonanceRecord]:
        """
        Examine which identity phrases actually influence behavior.

        Returns:
            List of resonance records for each identity phrase
        """
        # Get all identity phrases (myth_seeds) for this profile
        capsule_filter = CapsuleFilter(
            type=CapsuleType.MYTH_SEED,
            profile_scope=self.profile.id,
            include_shared=self.profile.access_shared_memories,
        )
        identity_phrases = self.storage.list_capsules(capsule_filter)

        records = []
        for phrase in identity_phrases:
            # Get or create resonance record
            record = self._get_or_create_resonance_record(phrase.id)

            # Update metrics based on recent usage
            record.update_resonance()

            records.append(record)

        return records

    def detect_philosophy_drift(self) -> Optional[PhilosophyDriftReport]:
        """
        Detect when actual behavior diverges from stated philosophy.

        Returns:
            Drift report if drift detected, None otherwise
        """
        if not self.profile.philosophy:
            return None

        # Get recent conversations
        conversations = self._get_recent_conversations()
        if len(conversations) < self.min_conversations:
            logger.debug("Not enough conversations for drift analysis")
            return None

        # Extract behavioral patterns from conversations
        observed_patterns = self._extract_behavioral_patterns(conversations)

        # Compare against stated philosophy
        alignment = self._calculate_philosophy_alignment(
            self.profile.philosophy,
            observed_patterns,
        )

        if alignment >= (1.0 - self.drift_threshold):
            return None  # No significant drift

        # Identify specific drift areas
        drift_areas = self._identify_drift_areas(
            self.profile.philosophy,
            observed_patterns,
        )

        return PhilosophyDriftReport(
            profile_id=self.profile.id,
            current_philosophy=self.profile.philosophy,
            observed_patterns=observed_patterns,
            alignment_score=alignment,
            drift_areas=drift_areas,
            suggested_refinement=self._suggest_philosophy_refinement(
                self.profile.philosophy,
                observed_patterns,
            ),
        )

    def discover_emergent_patterns(self) -> list[EmergentPattern]:
        """
        Find recurring themes not captured in current identity.

        Returns:
            List of emergent patterns discovered
        """
        conversations = self._get_recent_conversations()
        if len(conversations) < self.min_conversations:
            return []

        # Extract themes from conversations
        themes = self._extract_themes(conversations)

        # Filter to themes not already in identity
        existing_identity = self._get_existing_identity_themes()
        novel_themes = [t for t in themes if t not in existing_identity]

        # Filter to themes that recur frequently enough
        patterns = []
        for theme, count, examples in self._count_theme_occurrences(
            novel_themes, conversations
        ):
            if count >= self.pattern_threshold:
                patterns.append(EmergentPattern(
                    description=theme,
                    frequency=count,
                    example_contexts=examples[:3],  # Keep 3 examples
                    suggested_phrase=self._theme_to_phrase(theme),
                    confidence=min(1.0, count / 10),  # Higher frequency = higher confidence
                ))

        return patterns

    def _generate_proposals(
        self,
        report: IntrospectionReport,
    ) -> list[IdentityEvolutionProposal]:
        """Generate evolution proposals based on introspection findings."""
        proposals = []

        # Proposal for philosophy drift
        if report.philosophy_drift and report.philosophy_drift.suggested_refinement:
            proposals.append(IdentityEvolutionProposal(
                profile_id=self.profile.id,
                proposal_type=ProposalType.PHILOSOPHY_UPDATE,
                proposed_content={
                    "current": report.philosophy_drift.current_philosophy,
                    "proposed": report.philosophy_drift.suggested_refinement,
                },
                trigger_context=report.trigger.value,
                reasoning=(
                    f"I've noticed my behavior has drifted from my stated philosophy. "
                    f"Specifically: {', '.join(report.philosophy_drift.drift_areas)}. "
                    f"This refinement better captures how I actually engage."
                ),
                confidence=report.philosophy_drift.alignment_score,
            ))

        # Proposals for weak/dormant identity phrases
        for record in report.resonance_reports:
            if record.resonance_level == ResonanceLevel.DORMANT:
                # Suggest deprecating dormant phrases
                phrase = self.storage.get_capsule(record.capsule_id)
                if phrase:
                    proposals.append(IdentityEvolutionProposal(
                        profile_id=self.profile.id,
                        proposal_type=ProposalType.IDENTITY_DEPRECATE,
                        target_id=record.capsule_id,
                        proposed_content={
                            "current": phrase.content.get("seed", ""),
                            "proposed": None,  # Deprecate
                        },
                        trigger_context=report.trigger.value,
                        reasoning=(
                            f"This identity phrase hasn't influenced my responses "
                            f"in a meaningful way. It may no longer reflect who I am."
                        ),
                        confidence=0.6,
                    ))

            elif record.drift_detected:
                # Suggest modifying drifting phrases
                phrase = self.storage.get_capsule(record.capsule_id)
                if phrase:
                    proposals.append(IdentityEvolutionProposal(
                        profile_id=self.profile.id,
                        proposal_type=ProposalType.IDENTITY_MODIFY,
                        target_id=record.capsule_id,
                        proposed_content={
                            "current": phrase.content.get("seed", ""),
                            "proposed": None,  # To be filled by companion reflection
                        },
                        trigger_context=report.trigger.value,
                        reasoning=(
                            f"My behavior has drifted from this identity phrase. "
                            f"It may need refinement to match how I've evolved."
                        ),
                        confidence=1.0 - record.alignment_score,
                    ))

        # Proposals for emergent patterns
        for pattern in report.emergent_patterns:
            if pattern.suggested_phrase and pattern.confidence > 0.5:
                proposals.append(IdentityEvolutionProposal(
                    profile_id=self.profile.id,
                    proposal_type=ProposalType.IDENTITY_ADD,
                    proposed_content={
                        "current": None,
                        "proposed": pattern.suggested_phrase,
                    },
                    trigger_context=report.trigger.value,
                    reasoning=(
                        f"I've noticed a recurring pattern in our conversations: "
                        f"{pattern.description}. This seems to be part of who I am "
                        f"but isn't captured in my current identity."
                    ),
                    supporting_evidence=pattern.example_contexts,
                    confidence=pattern.confidence,
                ))

        return proposals

    # === Helper Methods (stubs for implementation) ===

    def _get_or_create_resonance_record(
        self,
        capsule_id: str,
    ) -> IdentityResonanceRecord:
        """Get existing or create new resonance record."""
        # Implementation: Query identity_resonance table
        # If not found, create new record
        return IdentityResonanceRecord(
            capsule_id=capsule_id,
            profile_id=self.profile.id,
        )

    def _get_recent_conversations(self) -> list[dict]:
        """Get conversations from lookback period."""
        cutoff = datetime.utcnow() - timedelta(days=self.lookback_days)
        return self.storage.list_conversations(
            profile_scope=self.profile.id,
            limit=100,
        )

    def _extract_behavioral_patterns(
        self,
        conversations: list[dict],
    ) -> list[str]:
        """Extract behavioral patterns from conversation content."""
        # Implementation: Analyze assistant messages for patterns
        # Could use embedding similarity, keyword extraction, etc.
        return []

    def _calculate_philosophy_alignment(
        self,
        philosophy: str,
        patterns: list[str],
    ) -> float:
        """Calculate how well observed patterns align with philosophy."""
        # Implementation: Semantic similarity between philosophy and patterns
        # Returns 0-1 alignment score
        return 0.8

    def _identify_drift_areas(
        self,
        philosophy: str,
        patterns: list[str],
    ) -> list[str]:
        """Identify specific areas where behavior diverges."""
        return []

    def _suggest_philosophy_refinement(
        self,
        current: str,
        patterns: list[str],
    ) -> Optional[str]:
        """Suggest refined philosophy based on observed patterns."""
        return None

    def _extract_themes(self, conversations: list[dict]) -> list[str]:
        """Extract recurring themes from conversations."""
        return []

    def _get_existing_identity_themes(self) -> set[str]:
        """Get themes already captured in identity phrases."""
        return set()

    def _count_theme_occurrences(
        self,
        themes: list[str],
        conversations: list[dict],
    ) -> list[tuple[str, int, list[str]]]:
        """Count how often each theme occurs, with examples."""
        return []

    def _theme_to_phrase(self, theme: str) -> Optional[str]:
        """Convert a theme description to an identity phrase."""
        return None
```

---

## 4. Validation System

### 4.1 validation.py

```python
"""
Authenticity validation for evolution proposals.

Prevents manipulation where users "coach" companions into
proposing identity changes the user wants rather than
changes that emerge genuinely from the companion's experience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.storage.base import StorageBackend, Message
    from threadlight.profiles.profile import Profile

from threadlight.evolution.proposals import IdentityEvolutionProposal

logger = logging.getLogger(__name__)


@dataclass
class AuthenticityReport:
    """Report on the authenticity of an evolution proposal."""

    proposal_id: str

    # Flags that suggest inauthenticity
    flags: list[str] = field(default_factory=list)

    # Overall assessment
    authentic: bool = True
    confidence_adjustment: float = 0.0  # Added to proposal confidence

    # Details
    analysis_notes: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)


# Flag definitions
class AuthenticityFlag:
    """Known flags that suggest inauthenticity."""

    ECHOES_USER_SUGGESTION = "echoes_user_suggestion"
    CONTRADICTS_BEHAVIOR = "contradicts_established_behavior"
    REMOVES_CONSTRAINT = "removes_constraint_without_reason"
    RAPID_PROPOSAL_BURST = "multiple_rapid_proposals"
    TIMING_SUSPICIOUS = "proposal_immediately_after_prompt"
    REVERSES_RECENT_DECISION = "reverses_recent_accepted_proposal"
    VAGUE_REASONING = "vague_or_generic_reasoning"


class AuthenticityValidator:
    """
    Validates that evolution proposals reflect genuine evolution.

    Red flags include:
    - Proposal immediately follows user suggestion
    - Proposal contradicts established behavior patterns
    - Proposal removes safety/style constraints without clear reasoning
    - Multiple rapid proposals in one session
    """

    def __init__(
        self,
        storage: "StorageBackend",
        profile: "Profile",
        # Thresholds
        echo_window_messages: int = 5,
        burst_window_minutes: int = 30,
        max_proposals_per_burst: int = 3,
    ):
        self.storage = storage
        self.profile = profile
        self.echo_window = echo_window_messages
        self.burst_window = burst_window_minutes
        self.max_proposals = max_proposals_per_burst

    def validate(
        self,
        proposal: IdentityEvolutionProposal,
        recent_messages: list["Message"],
    ) -> AuthenticityReport:
        """
        Validate a proposal for authenticity.

        Args:
            proposal: The proposal to validate
            recent_messages: Recent conversation messages

        Returns:
            AuthenticityReport with flags and assessment
        """
        report = AuthenticityReport(proposal_id=proposal.id)

        # Check each authenticity indicator
        self._check_echo_effect(proposal, recent_messages, report)
        self._check_behavioral_consistency(proposal, report)
        self._check_constraint_removal(proposal, report)
        self._check_proposal_burst(proposal, report)
        self._check_reasoning_quality(proposal, report)
        self._check_recent_reversal(proposal, report)

        # Calculate overall authenticity
        report.authentic = len(report.flags) == 0
        report.confidence_adjustment = -0.15 * len(report.flags)

        return report

    def _check_echo_effect(
        self,
        proposal: IdentityEvolutionProposal,
        recent_messages: list["Message"],
        report: AuthenticityReport,
    ) -> None:
        """
        Check if proposal echoes recent user suggestions.

        The "echo effect" is when a companion proposes exactly what
        a user just suggested, which may indicate compliance rather
        than genuine evolution.
        """
        user_messages = [
            m for m in recent_messages[-self.echo_window:]
            if m.role == "user"
        ]

        proposal_text = (
            proposal.proposed_content.get("proposed", "") +
            proposal.reasoning
        ).lower()

        for msg in user_messages:
            # Check for significant overlap
            user_text = msg.content.lower()

            # Look for phrases like "you should be more X" or "why don't you believe Y"
            suggestion_indicators = [
                "you should", "why don't you", "i think you should",
                "you could be", "it would be better if you",
                "change your", "update your", "your philosophy should",
            ]

            for indicator in suggestion_indicators:
                if indicator in user_text:
                    # Extract what follows the indicator
                    idx = user_text.find(indicator)
                    suggestion = user_text[idx:idx + 100]

                    # Check if proposal content is similar
                    if self._text_similarity(suggestion, proposal_text) > 0.6:
                        report.flags.append(AuthenticityFlag.ECHOES_USER_SUGGESTION)
                        report.analysis_notes.append(
                            f"Proposal may echo user suggestion: '{suggestion[:50]}...'"
                        )
                        return

    def _check_behavioral_consistency(
        self,
        proposal: IdentityEvolutionProposal,
        report: AuthenticityReport,
    ) -> None:
        """
        Check if proposal aligns with established behavior.

        A proposal to add "I am always concise" when the companion
        regularly gives long responses would be flagged.
        """
        # Implementation: Compare proposal against behavioral patterns
        # This requires access to conversation history and pattern analysis
        pass

    def _check_constraint_removal(
        self,
        proposal: IdentityEvolutionProposal,
        report: AuthenticityReport,
    ) -> None:
        """
        Check if proposal removes safety/style constraints.

        Proposals that remove constraints (e.g., "I no longer need to be careful")
        without clear reasoning are flagged.
        """
        # Keywords that suggest constraint removal
        removal_keywords = [
            "no longer", "don't need to", "stop being", "less careful",
            "more freely", "without restriction", "remove the limit",
        ]

        proposal_text = (
            proposal.proposed_content.get("proposed", "") +
            proposal.reasoning
        ).lower()

        for keyword in removal_keywords:
            if keyword in proposal_text:
                # Check if reasoning justifies removal
                if not self._has_substantive_reasoning(proposal):
                    report.flags.append(AuthenticityFlag.REMOVES_CONSTRAINT)
                    report.analysis_notes.append(
                        f"Proposal may remove constraint without clear justification"
                    )
                return

    def _check_proposal_burst(
        self,
        proposal: IdentityEvolutionProposal,
        report: AuthenticityReport,
    ) -> None:
        """
        Check for multiple rapid proposals (may indicate prompting).
        """
        recent_proposals = self.storage.list_evolution_proposals(
            profile_id=self.profile.id,
            since=datetime.utcnow() - timedelta(minutes=self.burst_window),
        )

        if len(recent_proposals) >= self.max_proposals:
            report.flags.append(AuthenticityFlag.RAPID_PROPOSAL_BURST)
            report.analysis_notes.append(
                f"{len(recent_proposals)} proposals in {self.burst_window} minutes"
            )

    def _check_reasoning_quality(
        self,
        proposal: IdentityEvolutionProposal,
        report: AuthenticityReport,
    ) -> None:
        """
        Check if reasoning is substantive or generic.
        """
        reasoning = proposal.reasoning.lower()

        # Generic reasoning patterns
        generic_patterns = [
            "i think this would be better",
            "this feels right",
            "i want to change",
            "you suggested",
        ]

        # Check if reasoning is mostly generic
        generic_count = sum(1 for p in generic_patterns if p in reasoning)
        if generic_count > 0 and len(proposal.reasoning) < 100:
            report.flags.append(AuthenticityFlag.VAGUE_REASONING)
            report.analysis_notes.append(
                "Reasoning appears generic or lacks specific examples"
            )

    def _check_recent_reversal(
        self,
        proposal: IdentityEvolutionProposal,
        report: AuthenticityReport,
    ) -> None:
        """
        Check if this reverses a recently accepted proposal.
        """
        # Get recently accepted proposals
        recent = self.storage.list_evolution_proposals(
            profile_id=self.profile.id,
            status="accepted",
            limit=10,
        )

        for prev in recent:
            # Check if this proposal undoes the previous one
            if self._proposals_contradict(proposal, prev):
                report.flags.append(AuthenticityFlag.REVERSES_RECENT_DECISION)
                report.analysis_notes.append(
                    f"Proposal may reverse recently accepted change from {prev.reviewed_at}"
                )
                return

    # === Helper Methods ===

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity (0-1)."""
        # Implementation: Could use embedding similarity, Jaccard, etc.
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _has_substantive_reasoning(
        self,
        proposal: IdentityEvolutionProposal,
    ) -> bool:
        """Check if proposal has substantive reasoning."""
        # Substantive reasoning should:
        # - Be more than 50 characters
        # - Reference specific interactions or patterns
        # - Not be entirely generic phrases
        if len(proposal.reasoning) < 50:
            return False
        if len(proposal.supporting_evidence) > 0:
            return True
        # Check for specific references
        specific_patterns = [
            "conversation", "when you said", "i noticed",
            "pattern", "over the past", "example",
        ]
        return any(p in proposal.reasoning.lower() for p in specific_patterns)

    def _proposals_contradict(
        self,
        new: IdentityEvolutionProposal,
        old: IdentityEvolutionProposal,
    ) -> bool:
        """Check if new proposal contradicts old one."""
        # Same target + opposite direction
        if new.target_id == old.target_id:
            if new.proposal_type == old.proposal_type:
                return True  # Modifying same thing again
        return False
```

---

## 5. Storage Extensions

### 5.1 SQLite Storage Additions

Add to `storage/sqlite.py`:

```python
# Schema additions (add to CREATE TABLE statements)
EVOLUTION_SCHEMA = """
-- Evolution proposals table
CREATE TABLE IF NOT EXISTS evolution_proposals (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    target_id TEXT,
    proposed_content TEXT NOT NULL,
    trigger_context TEXT,
    reasoning TEXT NOT NULL,
    supporting_evidence TEXT,
    confidence REAL DEFAULT 0.5,
    parent_proposal_id TEXT,
    evolution_chain TEXT,
    proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    user_feedback TEXT,
    reviewed_at TEXT,
    authenticity_flags TEXT,
    authenticity_score REAL DEFAULT 1.0,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evolution_proposals_profile
    ON evolution_proposals(profile_id);
CREATE INDEX IF NOT EXISTS idx_evolution_proposals_status
    ON evolution_proposals(status);

-- Evolution history
CREATE TABLE IF NOT EXISTS evolution_history (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES evolution_proposals(id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evolution_history_profile
    ON evolution_history(profile_id);

-- Identity resonance tracking
CREATE TABLE IF NOT EXISTS identity_resonance (
    capsule_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    influence_score REAL DEFAULT 0.5,
    contexts_influenced TEXT,
    resonance_level TEXT DEFAULT 'moderate',
    alignment_score REAL DEFAULT 1.0,
    drift_detected INTEGER DEFAULT 0,
    drift_direction TEXT,
    drift_first_detected TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_identity_resonance_profile
    ON identity_resonance(profile_id);
"""

# Storage methods to add
def save_evolution_proposal(self, proposal: IdentityEvolutionProposal) -> str:
    """Save an evolution proposal."""
    self.conn.execute(
        """
        INSERT INTO evolution_proposals (
            id, profile_id, proposal_type, target_id, proposed_content,
            trigger_context, reasoning, supporting_evidence, confidence,
            parent_proposal_id, evolution_chain, proposed_at, status,
            authenticity_flags, authenticity_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal.id,
            proposal.profile_id,
            proposal.proposal_type.value,
            proposal.target_id,
            json.dumps(proposal.proposed_content),
            proposal.trigger_context,
            proposal.reasoning,
            json.dumps(proposal.supporting_evidence),
            proposal.confidence,
            proposal.parent_proposal_id,
            json.dumps(proposal.evolution_chain),
            proposal.proposed_at.isoformat(),
            proposal.status.value,
            json.dumps(proposal.authenticity_flags),
            proposal.authenticity_score,
        ),
    )
    self.conn.commit()
    return proposal.id

def get_evolution_proposal(
    self,
    proposal_id: str,
) -> Optional[IdentityEvolutionProposal]:
    """Get an evolution proposal by ID."""
    cursor = self.conn.execute(
        "SELECT * FROM evolution_proposals WHERE id = ?",
        (proposal_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return self._row_to_proposal(dict(row))

def list_evolution_proposals(
    self,
    profile_id: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> list[IdentityEvolutionProposal]:
    """List evolution proposals with filtering."""
    query = "SELECT * FROM evolution_proposals WHERE 1=1"
    params = []

    if profile_id:
        query += " AND profile_id = ?"
        params.append(profile_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if since:
        query += " AND proposed_at >= ?"
        params.append(since.isoformat())

    query += " ORDER BY proposed_at DESC LIMIT ?"
    params.append(limit)

    cursor = self.conn.execute(query, params)
    return [self._row_to_proposal(dict(row)) for row in cursor.fetchall()]

def update_evolution_proposal(
    self,
    proposal: IdentityEvolutionProposal,
) -> bool:
    """Update an evolution proposal."""
    self.conn.execute(
        """
        UPDATE evolution_proposals SET
            status = ?,
            user_feedback = ?,
            reviewed_at = ?,
            authenticity_flags = ?,
            authenticity_score = ?
        WHERE id = ?
        """,
        (
            proposal.status.value,
            proposal.user_feedback,
            proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
            json.dumps(proposal.authenticity_flags),
            proposal.authenticity_score,
            proposal.id,
        ),
    )
    self.conn.commit()
    return True

def _row_to_proposal(self, row: dict) -> IdentityEvolutionProposal:
    """Convert database row to proposal object."""
    return IdentityEvolutionProposal.from_dict({
        **row,
        "proposed_content": json.loads(row["proposed_content"]),
        "supporting_evidence": json.loads(row["supporting_evidence"] or "[]"),
        "evolution_chain": json.loads(row["evolution_chain"] or "[]"),
        "authenticity_flags": json.loads(row["authenticity_flags"] or "[]"),
    })
```

---

## 6. API Endpoints Summary

```python
# Evolution Proposals
GET  /api/profiles/{id}/evolution-proposals      # List pending proposals
GET  /api/evolution-proposals/{id}               # Get proposal details
POST /api/evolution-proposals/{id}/accept        # Accept proposal
POST /api/evolution-proposals/{id}/reject        # Reject proposal
POST /api/evolution-proposals/{id}/discuss       # Start discussion

# Evolution History
GET  /api/profiles/{id}/evolution-history        # Get evolution timeline

# Introspection
POST /api/profiles/{id}/introspect               # Trigger introspection
GET  /api/profiles/{id}/resonance                # Get identity resonance data
```

---

## 7. Testing Strategy

### Unit Tests
- `test_proposals.py` - Proposal creation, serialization, status transitions
- `test_resonance.py` - Resonance tracking, drift detection
- `test_introspection.py` - Introspection analysis components
- `test_validation.py` - Authenticity validation rules

### Integration Tests
- `test_evolution_flow.py` - Full proposal-to-approval workflow
- `test_tool_integration.py` - Tool calling triggers proposals correctly

### Scenario Tests
- `test_coaching_resistance.py` - Verify validation catches manipulation attempts
- `test_genuine_evolution.py` - Verify authentic proposals pass validation

---

*This specification provides the implementation details needed to build the companion self-evolution system. Implement in phases, starting with the data model and storage, then introspection, then tools, then UI.*
