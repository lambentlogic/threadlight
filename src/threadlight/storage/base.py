"""
Base classes for storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import uuid


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
from typing import Any, Optional, TYPE_CHECKING

from threadlight.capsules.base import MemoryCapsule, CapsuleType, MemoryTier, RetentionPolicy

if TYPE_CHECKING:
    from threadlight.profiles.profile import Profile


# ============================================================================
# Conversation History Data Classes
# ============================================================================


@dataclass
class Message:
    """A single message in a conversation."""

    id: str
    conversation_id: str
    role: str  # 'user', 'assistant', or 'system'
    content: str
    timestamp: datetime
    source: str = ""  # 'claude', 'chatgpt', 'local', etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    profile_id: Optional[str] = None  # Profile that generated/received this message
    model_used: Optional[str] = None  # Model that generated this message (for assistant messages)
    variant_group_id: Optional[str] = None  # Groups variant messages together (UUID)
    variant_index: int = 0  # Order within variant group (0 = first, 1 = second, etc.)

    def to_dict(self) -> dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "source": self.source,
            "metadata": self.metadata,
            "embedding": self.embedding,
            "profile_id": self.profile_id,
            "model_used": self.model_used,
            "variant_group_id": self.variant_group_id,
            "variant_index": self.variant_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Deserialize message from dictionary."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            id=data["id"],
            conversation_id=data["conversation_id"],
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            profile_id=data.get("profile_id"),
            model_used=data.get("model_used"),
            variant_group_id=data.get("variant_group_id"),
            variant_index=data.get("variant_index", 0),
        )


@dataclass
class Conversation:
    """A conversation containing multiple messages."""

    id: str
    name: str = ""
    summary: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    source: str = ""  # 'claude', 'chatgpt', 'local', etc.
    message_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    archived: bool = False
    model_scope: Optional[str] = None  # Model ID for per-model isolation (NULL = shared)
    profile_scope: Optional[str] = None  # Profile ID for profile-based scoping (NULL = shared)
    model: Optional[str] = None  # Display model name (e.g., "gpt-4o", "Claude Opus", "Hermes-4.3")
    # Group chat support: list of profile IDs participating in this conversation
    participant_profiles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize conversation to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
            "source": self.source,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "archived": self.archived,
            "model_scope": self.model_scope,
            "profile_scope": self.profile_scope,
            "model": self.model,
            "participant_profiles": self.participant_profiles,
        }

    def is_group_chat(self) -> bool:
        """Check if this is a group chat with multiple profiles."""
        return len(self.participant_profiles) > 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        """Deserialize conversation from dictionary."""
        created_at = data.get("created_at", "")
        updated_at = data.get("updated_at", "")

        if isinstance(created_at, str) and created_at:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created_at = _utc_now()

        if isinstance(updated_at, str) and updated_at:
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        else:
            updated_at = _utc_now()

        return cls(
            id=data["id"],
            name=data.get("name", ""),
            summary=data.get("summary", ""),
            created_at=created_at,
            updated_at=updated_at,
            source=data.get("source", ""),
            message_count=data.get("message_count", 0),
            metadata=data.get("metadata", {}),
            archived=data.get("archived", False),
            model_scope=data.get("model_scope"),
            profile_scope=data.get("profile_scope"),
            model=data.get("model"),
            participant_profiles=data.get("participant_profiles", []),
        )


@dataclass
class MessageSearchResult:
    """A message search result with context."""

    message: Message
    conversation_name: str
    relevance_score: float = 0.0
    context_before: list[Message] = field(default_factory=list)
    context_after: list[Message] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Format this result as a context string for prompts."""
        date_str = self.message.timestamp.strftime("%B %d, %Y")
        conv_name = self.conversation_name or "a previous conversation"
        role = "you mentioned" if self.message.role == "assistant" else "the user said"

        # Truncate content if too long
        content = self.message.content
        if len(content) > 300:
            content = content[:300] + "..."

        return f'(From "{conv_name}" on {date_str}: {role}: "{content}")'


# ============================================================================
# Filter Classes
# ============================================================================


@dataclass
class CapsuleFilter:
    """Filter criteria for capsule queries.

    Profile scope filtering notes:
        ``shared_only`` and ``profile_scope`` are mutually exclusive.  When
        ``shared_only=True``, only capsules with a NULL profile_scope are
        returned and any ``profile_scope`` value is ignored.
    """

    type: Optional[CapsuleType] = None
    types: Optional[list[CapsuleType]] = None
    entity: Optional[str] = None
    cue_phrase: Optional[str] = None
    min_presence_score: Optional[float] = None
    consent_confirmed: Optional[bool] = None
    retention: Optional[RetentionPolicy] = None
    memory_tier: Optional[MemoryTier] = None

    # Time filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    accessed_after: Optional[datetime] = None
    accessed_before: Optional[datetime] = None

    # Profile scope filters (for per-profile memory isolation)
    profile_scope: Optional[str] = None  # Filter by specific profile
    include_shared: bool = True  # Whether to include profile_scope=NULL (shared) capsules
    shared_only: bool = False  # If True, only return capsules with NULL profile_scope

    # Archive filter
    include_archived: bool = False  # Whether to include archived memories (default: hidden)

    # Deprecated: Use profile_scope instead (kept for backward compatibility)
    model_scope: Optional[str] = None  # Filter by specific model (deprecated)

    # Pagination
    limit: int = 100
    offset: int = 0

    # Sorting
    order_by: str = "last_accessed"  # last_accessed, created_at, presence_score
    order_desc: bool = True

    def __post_init__(self):
        """Handle backward compatibility for model_scope -> profile_scope migration."""
        # If model_scope is set but profile_scope is not, use model_scope
        if self.model_scope is not None and self.profile_scope is None:
            self.profile_scope = self.model_scope


@dataclass
class MemoryProposal:
    """A proposed memory waiting for consent."""

    id: str
    capsule_type: CapsuleType
    content: dict[str, Any]
    proposed_at: datetime = field(default_factory=_utc_now)
    source_message: str = ""
    status: str = "pending"  # pending, confirmed, rejected
    memory_tier: str = "semantic"  # strictly_anchored, anchored_decaying, semantic


# ============================================================================
# Memory Link Data Classes
# ============================================================================


@dataclass
class MemoryLink:
    """An explicit relational link between two memory capsules.

    Links represent typed relationships between memories, enabling
    traversal of connected memory graphs. Links can be directional
    (source -> target) or bidirectional.

    Attributes:
        id: Unique identifier for the link
        source_capsule_id: ID of the source capsule
        target_capsule_id: ID of the target capsule
        link_type: Relationship type (e.g., 'related', 'contradicts', 'supports')
        strength: Link strength from 0.0 to 1.0
        bidirectional: Whether the link applies in both directions
        notes: Optional human-readable notes about the relationship
        created_at: When the link was created
        created_by: Who created the link ('user', 'system', etc.)
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_capsule_id: str = ""
    target_capsule_id: str = ""
    link_type: str = "related"
    strength: float = 1.0
    bidirectional: bool = False
    notes: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    created_by: str = "user"

    def to_dict(self) -> dict[str, Any]:
        """Serialize link to dictionary."""
        return {
            "id": self.id,
            "source_capsule_id": self.source_capsule_id,
            "target_capsule_id": self.target_capsule_id,
            "link_type": self.link_type,
            "strength": self.strength,
            "bidirectional": self.bidirectional,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryLink":
        """Deserialize link from dictionary."""
        created_at = data.get("created_at", "")
        if isinstance(created_at, str) and created_at:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created_at = _utc_now()

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            source_capsule_id=data.get("source_capsule_id", ""),
            target_capsule_id=data.get("target_capsule_id", ""),
            link_type=data.get("link_type", "related"),
            strength=data.get("strength", 1.0),
            bidirectional=data.get("bidirectional", False),
            notes=data.get("notes", ""),
            created_at=created_at,
            created_by=data.get("created_by", "user"),
        )


@dataclass
class DeletedItem:
    """A deleted item stored in the trash/recycle bin for potential restoration.

    Deleted capsules and links are serialized and stored here before being
    hard-deleted from their main tables. Items are auto-purged after a
    configurable retention period (default 30 days).

    Attributes:
        id: Unique identifier for the trash entry
        item_type: Type of deleted item ('capsule', 'memory_link')
        item_id: Original ID of the deleted item
        item_data: JSON-serialized representation of the deleted item
        related_items: JSON-serialized related items (e.g., links for a capsule)
        deleted_at: When the item was deleted
        deleted_by: Who deleted the item
        auto_purge_at: When this item should be permanently removed
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_type: str = ""  # 'capsule', 'memory_link'
    item_id: str = ""  # original ID
    item_data: str = ""  # JSON serialized object
    related_items: str = ""  # JSON array of related items
    deleted_at: datetime = field(default_factory=_utc_now)
    deleted_by: str = ""
    auto_purge_at: datetime = field(
        default_factory=lambda: _utc_now() + timedelta(days=30)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deleted item to dictionary."""
        return {
            "id": self.id,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "item_data": self.item_data,
            "related_items": self.related_items,
            "deleted_at": self.deleted_at.isoformat() if isinstance(self.deleted_at, datetime) else self.deleted_at,
            "deleted_by": self.deleted_by,
            "auto_purge_at": self.auto_purge_at.isoformat() if isinstance(self.auto_purge_at, datetime) else self.auto_purge_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeletedItem":
        """Deserialize deleted item from dictionary."""
        deleted_at = data.get("deleted_at", "")
        if isinstance(deleted_at, str) and deleted_at:
            deleted_at = datetime.fromisoformat(deleted_at.replace("Z", "+00:00"))
        else:
            deleted_at = _utc_now()

        auto_purge_at = data.get("auto_purge_at", "")
        if isinstance(auto_purge_at, str) and auto_purge_at:
            auto_purge_at = datetime.fromisoformat(auto_purge_at.replace("Z", "+00:00"))
        else:
            auto_purge_at = _utc_now() + timedelta(days=30)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            item_type=data.get("item_type", ""),
            item_id=data.get("item_id", ""),
            item_data=data.get("item_data", ""),
            related_items=data.get("related_items", ""),
            deleted_at=deleted_at,
            deleted_by=data.get("deleted_by", ""),
            auto_purge_at=auto_purge_at,
        )


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    All storage implementations must provide these methods.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize storage (create tables, etc.)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close storage connections."""
        pass

    # Capsule CRUD

    @abstractmethod
    def save_capsule(self, capsule: MemoryCapsule) -> str:
        """
        Save a capsule to storage.
        Returns the capsule ID.
        """
        pass

    @abstractmethod
    def get_capsule(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """Get a capsule by ID."""
        pass

    @abstractmethod
    def update_capsule(self, capsule: MemoryCapsule) -> bool:
        """
        Update an existing capsule.
        Returns True if successful.
        """
        pass

    @abstractmethod
    def delete_capsule(self, capsule_id: str) -> bool:
        """
        Delete a capsule.
        Returns True if successful.
        """
        pass

    @abstractmethod
    def list_capsules(self, filter: Optional[CapsuleFilter] = None) -> list[MemoryCapsule]:
        """List capsules matching filter criteria."""
        pass

    @abstractmethod
    def search_by_cue(self, cue: str, limit: int = 5) -> list[MemoryCapsule]:
        """Search capsules by cue phrase match."""
        pass

    # Proposal management

    @abstractmethod
    def save_proposal(self, proposal: MemoryProposal) -> str:
        """Save a memory proposal."""
        pass

    @abstractmethod
    def get_proposal(self, proposal_id: str) -> Optional[MemoryProposal]:
        """Get a proposal by ID."""
        pass

    @abstractmethod
    def list_proposals(self, status: str = "pending") -> list[MemoryProposal]:
        """List proposals by status."""
        pass

    @abstractmethod
    def update_proposal_status(self, proposal_id: str, status: str) -> bool:
        """Update proposal status."""
        pass

    # Batch operations

    @abstractmethod
    def update_presence_scores(self, updates: dict[str, float]) -> int:
        """
        Batch update presence scores.
        Returns number of capsules updated.
        """
        pass

    @abstractmethod
    def get_capsules_for_decay(
        self,
        before: datetime,
        exclude_retention: list[RetentionPolicy] | None = None
    ) -> list[MemoryCapsule]:
        """Get capsules eligible for decay processing."""
        pass

    # Utility

    @abstractmethod
    def count_capsules(self, filter: Optional[CapsuleFilter] = None) -> int:
        """Count capsules matching filter."""
        pass

    @abstractmethod
    def export_all(self) -> list[dict[str, Any]]:
        """Export all capsules as dictionaries."""
        pass

    @abstractmethod
    def import_capsules(self, capsules: list[dict[str, Any]]) -> int:
        """
        Import capsules from dictionaries.
        Returns number imported.
        """
        pass

    # ========================================================================
    # Conversation History Operations
    # ========================================================================

    @abstractmethod
    def save_conversation(self, conversation: Conversation) -> str:
        """
        Save a conversation to storage.
        Returns the conversation ID.
        """
        pass

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        include_archived: bool = False,
        profile_scope: Optional[str] = None,
        include_shared: bool = True,
        # Deprecated: Use profile_scope instead
        model_scope: Optional[str] = None,
    ) -> list[Conversation]:
        """List conversations with optional filtering.

        Args:
            limit: Maximum conversations to return
            offset: Offset for pagination
            source: Filter by source (e.g., 'local', 'chatgpt')
            include_archived: Whether to include archived conversations
            profile_scope: Filter by profile ID (for per-profile isolation)
            include_shared: Whether to include conversations with profile_scope=NULL
            model_scope: Deprecated. Use profile_scope instead.
        """
        pass

    @abstractmethod
    def update_conversation(self, conversation: Conversation) -> bool:
        """Update an existing conversation."""
        pass

    @abstractmethod
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        pass

    @abstractmethod
    def save_message(self, message: Message) -> str:
        """
        Save a message to storage.
        Returns the message ID.
        """
        pass

    @abstractmethod
    def save_messages_batch(self, messages: list[Message]) -> int:
        """
        Save multiple messages in a batch.
        Returns number of messages saved.
        """
        pass

    @abstractmethod
    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        pass

    @abstractmethod
    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a conversation."""
        pass

    @abstractmethod
    def search_messages(
        self,
        query: str,
        limit: int = 20,
        source: Optional[str] = None,
    ) -> list[MessageSearchResult]:
        """
        Full-text search across all messages.
        Returns messages with conversation context.
        """
        pass

    @abstractmethod
    def count_messages(self, conversation_id: Optional[str] = None) -> int:
        """Count messages, optionally for a specific conversation."""
        pass

    @abstractmethod
    def count_conversations(self) -> int:
        """Count total conversations."""
        pass

    @abstractmethod
    def update_message(self, message: Message) -> bool:
        """Update an existing message."""
        pass

    @abstractmethod
    def delete_message(self, message_id: str) -> bool:
        """Delete a single message."""
        pass

    @abstractmethod
    def get_message_variants(self, variant_group_id: str) -> list[Message]:
        """
        Get all messages in a variant group, ordered by variant_index.

        Args:
            variant_group_id: The variant group UUID

        Returns:
            List of messages in the variant group, ordered by variant_index ascending
        """
        pass

    @abstractmethod
    def delete_messages_after(self, conversation_id: str, message_id: str) -> int:
        """Delete a message and all messages after it in a conversation."""
        pass

    # ========================================================================
    # Profile Operations
    # ========================================================================

    @abstractmethod
    def save_profile(self, profile: Profile) -> None:
        """
        Save a profile to storage.

        Args:
            profile: The profile to save
        """
        pass

    @abstractmethod
    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """
        Get a profile by ID.

        Args:
            profile_id: The profile ID

        Returns:
            The Profile, or None if not found
        """
        pass

    @abstractmethod
    def update_profile(self, profile: Profile) -> None:
        """
        Update an existing profile.

        Args:
            profile: The profile to update
        """
        pass

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        """
        Delete a profile.

        Args:
            profile_id: The profile ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_profiles(self) -> list[Profile]:
        """
        List all profiles.

        Returns:
            List of all profiles
        """
        pass

    # ========================================================================
    # Memory Link Operations
    # ========================================================================

    @abstractmethod
    def create_link(self, link: MemoryLink) -> str:
        """
        Create a link between two memory capsules.

        Args:
            link: The MemoryLink to create

        Returns:
            The link ID

        Raises:
            ValueError: If source and target are the same capsule (self-link),
                        if source or target capsule does not exist,
                        or if a duplicate link exists (same source+target+type)
        """
        pass

    @abstractmethod
    def get_link(self, link_id: str) -> Optional[MemoryLink]:
        """
        Get a link by ID.

        Args:
            link_id: The link ID

        Returns:
            The MemoryLink, or None if not found
        """
        pass

    @abstractmethod
    def get_links_for_capsule(
        self,
        capsule_id: str,
        direction: str = "both",
        link_types: Optional[list[str]] = None,
    ) -> list[MemoryLink]:
        """
        Get all links for a capsule.

        Args:
            capsule_id: The capsule ID
            direction: 'outgoing' (source), 'incoming' (target), or 'both'
            link_types: Optional filter by link type(s)

        Returns:
            List of matching MemoryLinks
        """
        pass

    @abstractmethod
    def delete_link(self, link_id: str) -> bool:
        """
        Delete a link (moves to trash).

        Args:
            link_id: The link ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def update_link(self, link: MemoryLink) -> bool:
        """
        Update an existing link.

        Args:
            link: The MemoryLink with updated fields

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    def get_linked_capsules(
        self,
        capsule_id: str,
        direction: str = "both",
        link_types: Optional[list[str]] = None,
        depth: int = 1,
    ) -> list[tuple[MemoryCapsule, MemoryLink, int]]:
        """
        Get capsules linked to a given capsule, with optional depth traversal.

        Args:
            capsule_id: The starting capsule ID
            direction: 'outgoing', 'incoming', or 'both'
            link_types: Optional filter by link type(s)
            depth: Maximum traversal depth (1 = direct links only)

        Returns:
            List of (capsule, link, depth) tuples where depth indicates
            how many hops away the capsule is
        """
        pass

    @abstractmethod
    def list_link_types(self) -> list[str]:
        """
        List all distinct link types currently in use.

        Returns:
            List of link type strings
        """
        pass

    # ========================================================================
    # Trash / Deleted Items Operations
    # ========================================================================

    @abstractmethod
    def restore_deleted_item(self, deleted_item_id: str) -> bool:
        """
        Restore a deleted item from trash.

        Deserializes the item from the deleted_items table and re-inserts
        it into the appropriate main table.

        Args:
            deleted_item_id: The trash entry ID

        Returns:
            True if restored, False if not found
        """
        pass

    @abstractmethod
    def list_deleted_items(
        self,
        item_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[DeletedItem]:
        """
        List items in the trash.

        Args:
            item_type: Optional filter by type ('capsule', 'memory_link')
            limit: Maximum items to return

        Returns:
            List of DeletedItem entries, newest first
        """
        pass

    @abstractmethod
    def purge_old_deleted_items(self, older_than_days: int = 30) -> int:
        """
        Permanently remove deleted items older than the specified age.

        Args:
            older_than_days: Remove items deleted more than this many days ago

        Returns:
            Number of items permanently purged
        """
        pass

    @abstractmethod
    def move_capsule_to_trash(self, capsule_id: str) -> bool:
        """
        Move a capsule and its associated links to trash before deletion.

        The capsule data and related links are serialized into a DeletedItem
        entry so they can be restored later if needed.

        Args:
            capsule_id: The ID of the capsule to move to trash

        Returns:
            True if moved to trash, False if capsule not found
        """
        pass

    @abstractmethod
    def permanently_delete_trash_item(self, deleted_item_id: str) -> bool:
        """
        Permanently delete a single item from the trash (no restore possible).

        Args:
            deleted_item_id: The trash entry ID to permanently remove

        Returns:
            True if deleted, False if not found
        """
        pass
