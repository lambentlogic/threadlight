"""
Memory orchestrator for Threadlight.

Coordinates all memory operations: storage, retrieval, decay, and consent.

High-level API for memory operations:
- recall(): Query and surface relevant memories
- create(): Propose new memories (requires consent)
- confirm_proposal(): Accept proposed memories
- invoke_ritual(): Trigger ritual hooks
- reinforce(): Strengthen specific memories
- run_decay(): Execute decay cycle
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import logging
import uuid

from threadlight.capsules.base import MemoryCapsule, CapsuleType, RetentionPolicy
from threadlight.capsules.factory import create_capsule, capsule_from_simple
from threadlight.storage.base import (
    StorageBackend,
    CapsuleFilter,
    MemoryProposal,
    Conversation,
    Message,
    MessageSearchResult,
)
from threadlight.decay.engine import DecayEngine

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    Tracks a conversation session for memory continuity.

    Sessions allow:
    - Grouping related interactions
    - Tracking which memories were accessed
    - Managing session-scoped (ephemeral) memories
    - Associating with a conversation for auto-save
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    message_count: int = 0
    capsules_accessed: list[str] = field(default_factory=list)
    capsules_created: list[str] = field(default_factory=list)
    rituals_invoked: list[str] = field(default_factory=list)
    active_ritual: Optional[str] = None  # Currently active ritual state
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_id: Optional[str] = None  # Associated conversation for auto-save

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    @property
    def duration_seconds(self) -> float:
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def record_access(self, capsule_id: str) -> None:
        """Record that a capsule was accessed in this session."""
        if capsule_id not in self.capsules_accessed:
            self.capsules_accessed.append(capsule_id)

    def record_creation(self, capsule_id: str) -> None:
        """Record that a capsule was created in this session."""
        if capsule_id not in self.capsules_created:
            self.capsules_created.append(capsule_id)

    def record_ritual(self, ritual_name: str) -> None:
        """Record that a ritual was invoked."""
        self.rituals_invoked.append(ritual_name)
        self.active_ritual = ritual_name

    def end(self) -> None:
        """End the session."""
        self.ended_at = datetime.utcnow()
        self.active_ritual = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "message_count": self.message_count,
            "capsules_accessed": self.capsules_accessed,
            "capsules_created": self.capsules_created,
            "rituals_invoked": self.rituals_invoked,
            "active_ritual": self.active_ritual,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class RitualInvocation:
    """Result of invoking a ritual."""

    ritual_name: str
    capsule: Optional[MemoryCapsule] = None
    response_template: Optional[str] = None
    state_effects: dict[str, Any] = field(default_factory=dict)
    matched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ritual_name": self.ritual_name,
            "capsule_id": self.capsule.id if self.capsule else None,
            "response_template": self.response_template,
            "state_effects": self.state_effects,
            "matched": self.matched,
        }


class MemoryOrchestrator:
    """
    Orchestrates memory operations for Threadlight.

    Provides a high-level interface for:
    - Creating and managing capsules
    - Retrieving relevant memories for context
    - Managing memory proposals and consent
    - Invoking rituals
    - Running decay cycles
    - Session tracking
    - Per-model memory isolation (optional)

    Example:
        orchestrator = MemoryOrchestrator(storage)

        # Start a session
        session = orchestrator.start_session()

        # Recall memories for a message
        memories = orchestrator.recall("Tell me about our friendship")

        # Invoke a ritual
        result = orchestrator.invoke_ritual("/snuggle")

        # End session
        orchestrator.end_session()
    """

    def __init__(
        self,
        storage: StorageBackend,
        decay_engine: Optional[DecayEngine] = None,
        auto_propose: bool = True,
        proposal_threshold: int = 3,
        enable_sessions: bool = True,
        per_model_isolation: bool = False,
        default_shared: bool = False,
        current_model: Optional[str] = None,
        # New profile-based settings
        per_profile_isolation: bool = False,
        current_profile: Optional[str] = None,
    ):
        self.storage = storage
        self.decay_engine = decay_engine or DecayEngine(storage)
        self.auto_propose = auto_propose
        self.proposal_threshold = proposal_threshold
        self.enable_sessions = enable_sessions

        # Per-profile memory isolation settings (preferred over per-model)
        self._per_profile_isolation = per_profile_isolation
        self._current_profile = current_profile

        # Per-model memory isolation settings (deprecated, use per-profile)
        self._per_model_isolation = per_model_isolation
        self._default_shared = default_shared
        self._current_model = current_model

        # Session tracking
        self._current_session: Optional[Session] = None
        self._session_history: list[Session] = []

        # Track interactions for auto-proposal
        self._interaction_count = 0
        self._pending_proposal_content: list[dict] = []

    # === Profile Scope Management ===

    @property
    def per_profile_isolation(self) -> bool:
        """Whether per-profile memory isolation is enabled."""
        return self._per_profile_isolation

    @per_profile_isolation.setter
    def per_profile_isolation(self, value: bool) -> None:
        """Set per-profile memory isolation."""
        self._per_profile_isolation = value

    @property
    def current_profile(self) -> Optional[str]:
        """Get the current profile ID for memory scoping."""
        return self._current_profile

    @current_profile.setter
    def current_profile(self, value: Optional[str]) -> None:
        """Set the current profile ID for memory scoping."""
        self._current_profile = value

    # === Model Scope Management (Deprecated - use profile scope) ===

    @property
    def per_model_isolation(self) -> bool:
        """Whether per-model memory isolation is enabled (deprecated)."""
        return self._per_model_isolation

    @per_model_isolation.setter
    def per_model_isolation(self, value: bool) -> None:
        """Set per-model memory isolation (deprecated)."""
        self._per_model_isolation = value

    @property
    def current_model(self) -> Optional[str]:
        """Get the current model ID for memory scoping (deprecated)."""
        return self._current_model

    @current_model.setter
    def current_model(self, value: Optional[str]) -> None:
        """Set the current model ID for memory scoping (deprecated)."""
        self._current_model = value

    @property
    def default_shared(self) -> bool:
        """Whether new memories are shared by default when isolation is enabled."""
        return self._default_shared

    @default_shared.setter
    def default_shared(self, value: bool) -> None:
        """Set whether new memories are shared by default."""
        self._default_shared = value

    def _get_effective_profile_scope(self, shared: Optional[bool] = None) -> Optional[str]:
        """
        Get the effective profile scope for a new memory.

        Args:
            shared: Explicit override - True means shared (no scope), False means profile-specific

        Returns:
            None if shared or isolation disabled, profile ID if profile-specific
        """
        # Prefer profile isolation over model isolation
        if self._per_profile_isolation:
            if shared is True:
                return None
            if shared is False:
                return self._current_profile
            # Use default behavior
            if self._default_shared:
                return None
            return self._current_profile

        # Fall back to model isolation for backward compatibility
        if self._per_model_isolation:
            if shared is True:
                return None
            if shared is False:
                return self._current_model
            # Use default behavior
            if self._default_shared:
                return None
            return self._current_model

        return None

    def _get_effective_model_scope(self, shared: Optional[bool] = None) -> Optional[str]:
        """
        Get the effective model scope for a new memory.

        Deprecated: Use _get_effective_profile_scope instead.

        Args:
            shared: Explicit override - True means shared (no scope), False means model-specific

        Returns:
            None if shared or isolation disabled, model ID if model-specific
        """
        if not self._per_model_isolation:
            return None

        if shared is True:
            return None

        if shared is False:
            return self._current_model

        # Use default behavior
        if self._default_shared:
            return None
        return self._current_model

    # === Capsule Management ===

    def create(
        self,
        type: str,
        content: dict[str, Any],
        cue_phrases: Optional[list[str]] = None,
        retention: str = "normal",
        consent_confirmed: bool = False,
        shared: Optional[bool] = None,
        model_scope: Optional[str] = None,
        profile_scope: Optional[str] = None,
        **kwargs: Any
    ) -> MemoryCapsule:
        """
        Create a new memory capsule.

        Args:
            type: Capsule type (relational, myth_seed, ritual, style, witness)
            content: Type-specific content dictionary
            cue_phrases: Phrases that trigger retrieval
            retention: Retention policy (sacred, normal, ephemeral)
            consent_confirmed: Whether user has confirmed this memory
            shared: Whether this memory should be shared across all profiles
                   (None = use default behavior based on config)
            model_scope: Deprecated - use profile_scope instead
            profile_scope: Explicit profile scope override
            **kwargs: Additional capsule fields

        Returns:
            The created MemoryCapsule
        """
        # Determine profile scope (prefer profile_scope, fall back to model_scope)
        effective_profile_scope = profile_scope or model_scope
        if effective_profile_scope is None:
            effective_profile_scope = self._get_effective_profile_scope(shared)

        capsule = capsule_from_simple(
            type=type,
            content=content,
            cue_phrases=cue_phrases or [],
            retention=RetentionPolicy(retention),
            consent_confirmed=consent_confirmed,
            profile_scope=effective_profile_scope,
            model_scope=effective_profile_scope,  # Keep model_scope synced for backward compat
            **kwargs
        )

        self.storage.save_capsule(capsule)
        logger.debug(f"Created capsule: {capsule.id} ({capsule.type.value}), profile_scope={effective_profile_scope}")

        return capsule

    def get(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """Get a capsule by ID."""
        capsule = self.storage.get_capsule(capsule_id)
        if capsule:
            # Touch to record access
            capsule.touch()
            self.storage.update_capsule(capsule)
        return capsule

    def update(self, capsule: MemoryCapsule) -> bool:
        """Update an existing capsule."""
        return self.storage.update_capsule(capsule)

    def delete(self, capsule_id: str, force: bool = False) -> bool:
        """
        Delete a capsule.

        Args:
            capsule_id: ID of capsule to delete
            force: If False, prevents deleting sacred memories

        Returns:
            True if deleted
        """
        if not force:
            capsule = self.storage.get_capsule(capsule_id)
            if capsule and capsule.retention == RetentionPolicy.SACRED:
                logger.warning(f"Cannot delete sacred capsule {capsule_id} without force=True")
                return False

        return self.storage.delete_capsule(capsule_id)

    def share_memory(self, capsule_id: str) -> bool:
        """
        Make a memory shared across all models (remove model scope).

        Args:
            capsule_id: ID of capsule to share

        Returns:
            True if successful
        """
        capsule = self.storage.get_capsule(capsule_id)
        if not capsule:
            return False

        capsule.model_scope = None
        return self.storage.update_capsule(capsule)

    def assign_memory_to_model(self, capsule_id: str, model_id: str) -> bool:
        """
        Assign a memory to a specific model.

        Args:
            capsule_id: ID of capsule to assign
            model_id: Model ID to assign to

        Returns:
            True if successful
        """
        capsule = self.storage.get_capsule(capsule_id)
        if not capsule:
            return False

        capsule.model_scope = model_id
        return self.storage.update_capsule(capsule)

    def copy_memory_to_model(self, capsule_id: str, target_model_id: str) -> Optional[MemoryCapsule]:
        """
        Copy a memory to another model (creates a new capsule).

        Args:
            capsule_id: ID of capsule to copy
            target_model_id: Model ID to copy to

        Returns:
            The new capsule, or None if source not found
        """
        source = self.storage.get_capsule(capsule_id)
        if not source:
            return None

        # Create a new capsule with the same content but different model scope
        return self.create(
            type=source.type.value,
            content=source.content.copy(),
            cue_phrases=source.cue_phrases.copy(),
            retention=source.retention.value,
            consent_confirmed=source.consent_confirmed,
            model_scope=target_model_id,
        )

    def get_memory_model_scope(self, capsule_id: str) -> Optional[str]:
        """
        Get the model scope of a memory.

        Args:
            capsule_id: ID of capsule

        Returns:
            Model ID if scoped, None if shared or not found
        """
        capsule = self.storage.get_capsule(capsule_id)
        if not capsule:
            return None
        return getattr(capsule, 'model_scope', None)

    def list(
        self,
        type: Optional[CapsuleType] = None,
        confirmed_only: bool = False,
        min_presence: float = 0.1,
        limit: int = 100,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
        profile_scope: Optional[str] = None,
    ) -> list[MemoryCapsule]:
        """List capsules with filtering.

        Args:
            type: Filter by capsule type
            confirmed_only: Only return confirmed capsules
            min_presence: Minimum presence score
            limit: Maximum results
            model_scope: Deprecated - use profile_scope instead
            include_shared: Whether to include shared memories
            profile_scope: Override profile scope for filtering (uses current if None)
        """
        # Determine effective scope for filtering (prefer profile, fall back to model)
        effective_scope = profile_scope or model_scope
        if effective_scope is None:
            if self._per_profile_isolation:
                effective_scope = self._current_profile
            elif self._per_model_isolation:
                effective_scope = self._current_model

        isolation_enabled = self._per_profile_isolation or self._per_model_isolation

        filter = CapsuleFilter(
            type=type,
            consent_confirmed=True if confirmed_only else None,
            min_presence_score=min_presence,
            limit=limit,
            profile_scope=effective_scope if isolation_enabled else None,
            include_shared=include_shared,
        )
        return self.storage.list_capsules(filter)

    # === Memory Retrieval ===

    def recall(
        self,
        cue: str,
        types: Optional[list[CapsuleType]] = None,
        limit: int = 5,
        min_presence: float = 0.3,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
        profile_scope: Optional[str] = None,
    ) -> list[MemoryCapsule]:
        """
        Recall memories matching a cue.

        This is the primary retrieval method for context injection.

        Args:
            cue: Text to match against cue phrases
            types: Limit to specific capsule types
            limit: Maximum capsules to return
            min_presence: Minimum presence score threshold
            model_scope: Deprecated - use profile_scope instead
            include_shared: Whether to include shared (profile_scope=NULL) memories
            profile_scope: Override profile scope for filtering (uses current if None)

        Returns:
            List of matching capsules, sorted by relevance
        """
        # Determine effective scope for filtering (prefer profile, fall back to model)
        effective_scope = profile_scope or model_scope
        if effective_scope is None:
            if self._per_profile_isolation:
                effective_scope = self._current_profile
            elif self._per_model_isolation:
                effective_scope = self._current_model

        # Search by cue phrase with profile/model scope filtering
        isolation_enabled = self._per_profile_isolation or self._per_model_isolation
        matches = self.storage.search_by_cue(
            cue,
            limit=limit * 2,
            profile_scope=effective_scope if isolation_enabled else None,
            include_shared=include_shared,
        )

        # Filter by type if specified
        if types:
            matches = [m for m in matches if m.type in types]

        # Filter by presence score
        matches = [m for m in matches if m.presence_score >= min_presence]

        # Touch accessed capsules and track in session
        for capsule in matches[:limit]:
            capsule.touch()
            self.storage.update_capsule(capsule)

            # Track in session
            if self._current_session:
                self._current_session.record_access(capsule.id)

        return matches[:limit]

    def recall_for_message(
        self,
        message: str,
        include_rituals: bool = True,
        include_style: bool = True,
        limit: int = 5,
        include_shared: bool = True,
    ) -> list[MemoryCapsule]:
        """
        Recall all relevant memories for a user message.

        Searches across all capsule types and combines results.
        This is the main method for retrieving context-relevant memories.

        Args:
            message: The user message to find relevant memories for
            include_rituals: Whether to check for ritual triggers
            include_style: Whether to include style profiles
            limit: Maximum capsules to return
            include_shared: Whether to include shared (profile_scope=NULL) memories.
                           Set to False for profiles with access_shared_memories=False.

        Returns:
            List of relevant capsules sorted by presence score
        """
        results = []

        # Track interaction
        self.record_interaction()

        # Extract potential cues from message
        words = message.lower().split()
        cues = [w for w in words if len(w) > 3]

        # Search each cue
        seen_ids = set()
        for cue in cues[:5]:  # Limit cue searches
            matches = self.recall(cue, limit=3, include_shared=include_shared)
            for m in matches:
                if m.id not in seen_ids:
                    results.append(m)
                    seen_ids.add(m.id)

        # Determine effective profile scope for ritual/style filtering
        isolation_enabled = self._per_profile_isolation or self._per_model_isolation
        effective_scope = None
        if isolation_enabled:
            effective_scope = self._current_profile or self._current_model

        # Check for ritual triggers
        if include_rituals:
            ritual_filter = CapsuleFilter(
                type=CapsuleType.RITUAL,
                consent_confirmed=True,
                profile_scope=effective_scope if isolation_enabled else None,
                include_shared=include_shared,
            )
            rituals = self.storage.list_capsules(ritual_filter)
            for ritual in rituals:
                # Rituals have a matches() method
                if hasattr(ritual, 'matches') and ritual.matches(message):
                    if ritual.id not in seen_ids:
                        results.append(ritual)
                        seen_ids.add(ritual.id)

                        # Track ritual access
                        if self._current_session:
                            self._current_session.record_access(ritual.id)

        # Include active style profile
        if include_style:
            style_filter = CapsuleFilter(
                type=CapsuleType.STYLE,
                limit=1,
                profile_scope=effective_scope if isolation_enabled else None,
                include_shared=include_shared,
            )
            styles = self.storage.list_capsules(style_filter)
            for style in styles:
                if style.id not in seen_ids:
                    results.append(style)
                    seen_ids.add(style.id)

        # Sort by presence score
        results.sort(key=lambda c: c.presence_score, reverse=True)

        return results[:limit]

    # === Proposal Management ===

    def propose(
        self,
        type: str,
        content: dict[str, Any],
        source_message: str = "",
    ) -> MemoryProposal:
        """
        Create a memory proposal for user consent.

        Proposals are not active until confirmed.
        """
        import uuid

        proposal = MemoryProposal(
            id=str(uuid.uuid4()),
            capsule_type=CapsuleType(type),
            content=content,
            proposed_at=datetime.utcnow(),
            source_message=source_message,
            status="pending",
        )

        self.storage.save_proposal(proposal)
        logger.debug(f"Created proposal: {proposal.id}")

        return proposal

    def confirm_proposal(self, proposal_id: str) -> Optional[MemoryCapsule]:
        """
        Confirm a proposal, creating an active capsule.

        Returns the created capsule.
        """
        proposal = self.storage.get_proposal(proposal_id)
        if not proposal:
            return None

        if proposal.status != "pending":
            logger.warning(f"Proposal {proposal_id} is not pending")
            return None

        # Create the capsule
        capsule = self.create(
            type=proposal.capsule_type.value,
            content=proposal.content,
            consent_confirmed=True,
            consent_origin="user_confirmed",
        )

        # Update proposal status
        self.storage.update_proposal_status(proposal_id, "confirmed")

        logger.info(f"Confirmed proposal {proposal_id} -> capsule {capsule.id}")
        return capsule

    def reject_proposal(self, proposal_id: str) -> bool:
        """Reject a memory proposal."""
        return self.storage.update_proposal_status(proposal_id, "rejected")

    def get_pending_proposals(self) -> list[MemoryProposal]:
        """Get all pending memory proposals."""
        return self.storage.list_proposals(status="pending")

    # === Decay Management ===

    def run_decay(self) -> dict[str, Any]:
        """Run a decay cycle and return statistics."""
        result = self.decay_engine.run_cycle()
        return {
            "processed": result.capsules_processed,
            "decayed": result.capsules_decayed,
            "dormant": result.capsules_dormant,
        }

    def revive(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """Revive a dormant capsule to full presence."""
        return self.decay_engine.revive_capsule(capsule_id)

    def get_dormant(self) -> list[MemoryCapsule]:
        """Get all dormant capsules."""
        return self.decay_engine.get_dormant_capsules()

    # === Ritual Invocation ===

    def invoke_ritual(
        self,
        ritual_trigger: str,
        context: Optional[str] = None,
    ) -> RitualInvocation:
        """
        Invoke a ritual by its trigger phrase or name.

        Rituals are repeated acts that hold emotion across time.
        When invoked, they trigger specific response patterns and
        may modify the current conversational state.

        Args:
            ritual_trigger: The trigger phrase (e.g., "/snuggle", "tea-time")
            context: Optional additional context for the ritual

        Returns:
            RitualInvocation with ritual details and response template

        Example:
            result = orchestrator.invoke_ritual("/snuggle")
            if result.matched:
                print(result.response_template)
        """
        result = RitualInvocation(ritual_name=ritual_trigger)

        # Find matching ritual capsule
        ritual_filter = CapsuleFilter(
            type=CapsuleType.RITUAL,
            consent_confirmed=True,
        )
        rituals = self.storage.list_capsules(ritual_filter)

        for ritual in rituals:
            if hasattr(ritual, 'matches') and ritual.matches(ritual_trigger):
                result.matched = True
                result.capsule = ritual

                # Get response template
                if hasattr(ritual, 'get_response_template'):
                    result.response_template = ritual.get_response_template()

                # Get state effects
                if hasattr(ritual, 'state_effects'):
                    result.state_effects = ritual.state_effects

                # Touch the ritual capsule (reinforces it)
                ritual.touch()
                self.storage.update_capsule(ritual)

                # Track in session
                if self._current_session:
                    self._current_session.record_ritual(ritual_trigger)
                    self._current_session.record_access(ritual.id)

                logger.info(f"Ritual invoked: {ritual_trigger} -> {ritual.id}")
                break

        if not result.matched:
            logger.debug(f"No matching ritual found for: {ritual_trigger}")
            # Still track the attempt
            if self._current_session:
                self._current_session.record_ritual(ritual_trigger)

        return result

    def get_active_ritual(self) -> Optional[str]:
        """Get the currently active ritual, if any."""
        if self._current_session:
            return self._current_session.active_ritual
        return None

    def clear_ritual_state(self) -> None:
        """Clear the active ritual state."""
        if self._current_session:
            self._current_session.active_ritual = None

    # === Reinforcement ===

    def reinforce(
        self,
        capsule_ids: list[str],
        strength: float = 0.2,
    ) -> dict[str, Any]:
        """
        Reinforce specific memories to strengthen their presence.

        Use this when memories should be retained longer, such as:
        - User explicitly marks a memory as important
        - Memory is accessed frequently in a short time
        - Related memories should decay together more slowly

        Args:
            capsule_ids: IDs of capsules to reinforce
            strength: Reinforcement strength (0.0 to 1.0)

        Returns:
            Dictionary with reinforcement statistics
        """
        result = self.decay_engine.reinforce(capsule_ids, strength)

        # Track in session
        if self._current_session:
            for cid in capsule_ids:
                self._current_session.record_access(cid)

        return result.to_dict()

    # === Session Management ===

    def start_session(self, metadata: Optional[dict[str, Any]] = None) -> Session:
        """
        Start a new conversation session.

        Sessions enable:
        - Grouping related interactions
        - Tracking memory access patterns
        - Managing ephemeral (session-scoped) memories

        Args:
            metadata: Optional metadata to attach to the session

        Returns:
            The new Session object
        """
        # End any existing session
        if self._current_session and self._current_session.is_active:
            self.end_session()

        self._current_session = Session(metadata=metadata or {})
        logger.info(f"Session started: {self._current_session.id}")
        return self._current_session

    def end_session(self) -> Optional[Session]:
        """
        End the current session.

        This will:
        - Mark the session as ended
        - Clean up ephemeral memories created in this session
        - Save session to history

        Returns:
            The ended Session, or None if no active session
        """
        if not self._current_session:
            return None

        self._current_session.end()

        # Clean up ephemeral memories from this session
        for capsule_id in self._current_session.capsules_created:
            capsule = self.storage.get_capsule(capsule_id)
            if capsule and capsule.retention == RetentionPolicy.EPHEMERAL:
                self.storage.delete_capsule(capsule_id)
                logger.debug(f"Cleaned up ephemeral capsule: {capsule_id}")

        # Save to history
        self._session_history.append(self._current_session)
        ended_session = self._current_session
        self._current_session = None

        logger.info(f"Session ended: {ended_session.id} (duration: {ended_session.duration_seconds:.1f}s)")
        return ended_session

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session, if any."""
        return self._current_session

    def get_session_history(self, limit: int = 10) -> list[Session]:
        """Get recent session history."""
        return self._session_history[-limit:]

    def record_interaction(self) -> None:
        """Record that an interaction occurred in the current session."""
        self._interaction_count += 1
        if self._current_session:
            self._current_session.message_count += 1

    # === Utility ===

    def export(self) -> list[dict[str, Any]]:
        """Export all capsules for backup."""
        return self.storage.export_all()

    def import_capsules(self, capsules: list[dict[str, Any]]) -> int:
        """Import capsules from backup."""
        return self.storage.import_capsules(capsules)

    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        all_filter = CapsuleFilter(limit=10000)
        capsules = self.storage.list_capsules(all_filter)

        by_type = {}
        for c in capsules:
            t = c.type.value
            by_type[t] = by_type.get(t, 0) + 1

        confirmed = sum(1 for c in capsules if c.consent_confirmed)
        dormant = sum(1 for c in capsules if c.presence_score <= 0.1)

        session_stats = None
        if self._current_session:
            session_stats = {
                "id": self._current_session.id,
                "message_count": self._current_session.message_count,
                "capsules_accessed": len(self._current_session.capsules_accessed),
                "rituals_invoked": len(self._current_session.rituals_invoked),
                "active_ritual": self._current_session.active_ritual,
                "conversation_id": self._current_session.conversation_id,
            }

        return {
            "total": len(capsules),
            "by_type": by_type,
            "confirmed": confirmed,
            "pending_consent": len(capsules) - confirmed,
            "dormant": dormant,
            "pending_proposals": len(self.get_pending_proposals()),
            "decay_stats": self.decay_engine.get_decay_stats() if hasattr(self.decay_engine, 'get_decay_stats') else None,
            "session": session_stats,
            "total_sessions": len(self._session_history),
        }

    # === Conversation Management ===

    def create_conversation(
        self,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        model_scope: Optional[str] = None,
    ) -> Conversation:
        """
        Create a new conversation record.

        Args:
            name: Conversation name (auto-generated if not provided)
            summary: Optional summary of the conversation
            metadata: Additional metadata
            model_scope: Model to scope conversation to (None = use current model if isolation enabled)

        Returns:
            The created Conversation
        """
        # Determine model scope for conversation
        effective_scope = model_scope
        if effective_scope is None and self._per_model_isolation:
            effective_scope = self._current_model

        conv = Conversation(
            id=str(uuid.uuid4()),
            name=name or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            summary=summary or "",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            source="local",
            message_count=0,
            metadata=metadata or {},
            model_scope=effective_scope,
        )

        self.storage.save_conversation(conv)
        logger.debug(f"Created conversation: {conv.id}, model_scope={effective_scope}")
        return conv

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.storage.get_conversation(conversation_id)

    def get_current_conversation(self) -> Optional[Conversation]:
        """Get the current session's conversation, if any."""
        if self._current_session and self._current_session.conversation_id:
            return self.storage.get_conversation(self._current_session.conversation_id)
        return None

    def update_conversation(
        self,
        conversation_id: str,
        name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> bool:
        """
        Update a conversation's metadata.

        Args:
            conversation_id: ID of conversation to update
            name: New name (if provided)
            summary: New summary (if provided)

        Returns:
            True if updated successfully
        """
        conv = self.storage.get_conversation(conversation_id)
        if not conv:
            return False

        if name is not None:
            conv.name = name
        if summary is not None:
            conv.summary = summary

        return self.storage.update_conversation(conv)

    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
    ) -> list[Conversation]:
        """List conversations with optional filtering.

        Args:
            limit: Maximum conversations to return
            offset: Offset for pagination
            source: Filter by source
            model_scope: Filter by model scope (uses current if None and isolation enabled)
            include_shared: Whether to include shared conversations
        """
        # Determine effective model scope for filtering
        effective_scope = model_scope
        if effective_scope is None and self._per_model_isolation:
            effective_scope = self._current_model

        return self.storage.list_conversations(
            limit=limit,
            offset=offset,
            source=source,
            model_scope=effective_scope if self._per_model_isolation else None,
            include_shared=include_shared,
        )

    def save_message(
        self,
        role: str,
        content: str,
        conversation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Message]:
        """
        Save a message to a conversation.

        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            conversation_id: Target conversation (uses current session's if not provided)
            metadata: Additional metadata

        Returns:
            The saved Message, or None if no conversation available
        """
        # Determine conversation ID
        conv_id = conversation_id
        if not conv_id and self._current_session:
            conv_id = self._current_session.conversation_id

        if not conv_id:
            logger.warning("No conversation ID available for saving message")
            return None

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            source="local",
            metadata=metadata or {},
        )

        try:
            self.storage.save_message(msg)

            # Update conversation metadata
            conv = self.storage.get_conversation(conv_id)
            if conv:
                conv.message_count += 1
                conv.updated_at = datetime.utcnow()
                self.storage.update_conversation(conv)

            logger.debug(f"Saved message {msg.id} to conversation {conv_id}")
            return msg
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return None

    def save_message_pair(
        self,
        user_message: str,
        assistant_response: str,
        conversation_id: Optional[str] = None,
        user_metadata: Optional[dict[str, Any]] = None,
        assistant_metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Optional[Message], Optional[Message]]:
        """
        Save a user message and assistant response pair.

        This is a convenience method for saving both messages in a chat exchange.

        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            conversation_id: Target conversation (uses current session's if not provided)
            user_metadata: Metadata for user message
            assistant_metadata: Metadata for assistant message

        Returns:
            Tuple of (user_message, assistant_message), either may be None on failure
        """
        user_msg = self.save_message(
            role="user",
            content=user_message,
            conversation_id=conversation_id,
            metadata=user_metadata,
        )

        assistant_msg = self.save_message(
            role="assistant",
            content=assistant_response,
            conversation_id=conversation_id,
            metadata=assistant_metadata,
        )

        return (user_msg, assistant_msg)

    def get_conversation_messages(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: Target conversation (uses current session's if not provided)
            limit: Maximum messages to return
            offset: Offset for pagination

        Returns:
            List of messages in chronological order
        """
        conv_id = conversation_id
        if not conv_id and self._current_session:
            conv_id = self._current_session.conversation_id

        if not conv_id:
            return []

        return self.storage.get_messages(conv_id, limit=limit, offset=offset)

    def search_messages(
        self,
        query: str,
        limit: int = 20,
        source: Optional[str] = None,
    ) -> list[MessageSearchResult]:
        """
        Search messages across all conversations.

        Args:
            query: Search query
            limit: Maximum results
            source: Optional source filter

        Returns:
            List of search results with context
        """
        return self.storage.search_messages(query, limit=limit, source=source)

    def get_recent_messages_for_context(
        self,
        limit: int = 20,
        conversation_id: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """
        Get recent messages formatted for chat context.

        Returns messages in the format expected by chat() history parameter.

        Args:
            limit: Maximum messages to return
            conversation_id: Target conversation (uses current session's if not provided)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        messages = self.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
        )

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role in ("user", "assistant")
        ]

    def attach_conversation_to_session(self, conversation_id: Optional[str] = None) -> bool:
        """
        Attach a conversation to the current session.

        If no conversation_id is provided, creates a new conversation.

        Args:
            conversation_id: ID of existing conversation to attach

        Returns:
            True if successful
        """
        if not self._current_session:
            logger.warning("No active session to attach conversation to")
            return False

        if conversation_id:
            # Verify conversation exists
            conv = self.storage.get_conversation(conversation_id)
            if not conv:
                logger.warning(f"Conversation {conversation_id} not found")
                return False
            self._current_session.conversation_id = conversation_id
        else:
            # Create new conversation
            conv = self.create_conversation(
                metadata={"session_id": self._current_session.id}
            )
            self._current_session.conversation_id = conv.id

        logger.debug(f"Attached conversation {self._current_session.conversation_id} to session")
        return True
