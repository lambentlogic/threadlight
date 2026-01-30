"""
In-memory storage backend for Threadlight.

Useful for testing and ephemeral sessions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import uuid

from threadlight.capsules.base import MemoryCapsule, CapsuleType, RetentionPolicy
from threadlight.capsules.factory import create_capsule
from threadlight.storage.base import (
    StorageBackend,
    CapsuleFilter,
    MemoryProposal,
    Message,
    Conversation,
    MessageSearchResult,
)
from threadlight.profiles.profile import Profile


class InMemoryStorage(StorageBackend):
    """In-memory storage for testing and ephemeral use."""

    def __init__(self, **kwargs: Any):
        self.capsules: dict[str, MemoryCapsule] = {}
        self.proposals: dict[str, MemoryProposal] = {}
        self.conversations: dict[str, Conversation] = {}
        self.messages: dict[str, Message] = {}
        self.profiles: dict[str, Profile] = {}

    def initialize(self) -> None:
        """Nothing to initialize for in-memory storage."""
        pass

    def close(self) -> None:
        """Clear storage on close."""
        self.capsules.clear()
        self.proposals.clear()
        self.conversations.clear()
        self.messages.clear()
        self.profiles.clear()

    # Capsule CRUD

    def save_capsule(self, capsule: MemoryCapsule) -> str:
        """Save a capsule to memory."""
        self.capsules[capsule.id] = capsule
        return capsule.id

    def get_capsule(self, capsule_id: str) -> Optional[MemoryCapsule]:
        """Get a capsule by ID."""
        return self.capsules.get(capsule_id)

    def update_capsule(self, capsule: MemoryCapsule) -> bool:
        """Update an existing capsule."""
        if capsule.id not in self.capsules:
            return False
        capsule.updated_at = datetime.utcnow()
        self.capsules[capsule.id] = capsule
        return True

    def delete_capsule(self, capsule_id: str) -> bool:
        """Delete a capsule."""
        if capsule_id not in self.capsules:
            return False
        del self.capsules[capsule_id]
        return True

    def list_capsules(self, filter: Optional[CapsuleFilter] = None) -> list[MemoryCapsule]:
        """List capsules matching filter criteria."""
        capsules = list(self.capsules.values())

        if filter:
            if filter.type:
                capsules = [c for c in capsules if c.type == filter.type]

            if filter.types:
                capsules = [c for c in capsules if c.type in filter.types]

            if filter.min_presence_score is not None:
                capsules = [c for c in capsules if c.presence_score >= filter.min_presence_score]

            if filter.consent_confirmed is not None:
                capsules = [c for c in capsules if c.consent_confirmed == filter.consent_confirmed]

            if filter.retention:
                capsules = [c for c in capsules if c.retention == filter.retention]

            if filter.created_after:
                capsules = [c for c in capsules if c.created_at >= filter.created_after]

            if filter.created_before:
                capsules = [c for c in capsules if c.created_at <= filter.created_before]

            if filter.accessed_after:
                capsules = [c for c in capsules if c.last_accessed >= filter.accessed_after]

            if filter.accessed_before:
                capsules = [c for c in capsules if c.last_accessed <= filter.accessed_before]

            # Profile scope filtering (profile_scope takes precedence, model_scope via __post_init__)
            if filter.profile_scope is not None:
                if filter.include_shared:
                    capsules = [
                        c for c in capsules
                        if getattr(c, 'profile_scope', None) == filter.profile_scope
                        or getattr(c, 'profile_scope', None) is None
                    ]
                else:
                    capsules = [
                        c for c in capsules
                        if getattr(c, 'profile_scope', None) == filter.profile_scope
                    ]

            # Sorting
            if filter.order_by == "last_accessed":
                capsules.sort(key=lambda c: c.last_accessed, reverse=filter.order_desc)
            elif filter.order_by == "created_at":
                capsules.sort(key=lambda c: c.created_at, reverse=filter.order_desc)
            elif filter.order_by == "presence_score":
                capsules.sort(key=lambda c: c.presence_score, reverse=filter.order_desc)

            # Pagination
            capsules = capsules[filter.offset:filter.offset + filter.limit]
        else:
            # Default: sort by last_accessed, limit 100
            capsules.sort(key=lambda c: c.last_accessed, reverse=True)
            capsules = capsules[:100]

        return capsules

    def search_by_cue(
        self,
        cue: str,
        limit: int = 5,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
        profile_scope: Optional[str] = None,
    ) -> list[MemoryCapsule]:
        """Search capsules by cue phrase match.

        Args:
            cue: Search query string
            limit: Maximum results to return
            model_scope: Deprecated - use profile_scope instead
            include_shared: Whether to include shared (NULL scope) capsules
            profile_scope: Profile ID to filter by (takes precedence over model_scope)
        """
        cue_lower = cue.lower()
        matches = []

        # Use profile_scope if provided, fall back to model_scope for backward compatibility
        effective_scope = profile_scope if profile_scope is not None else model_scope

        for capsule in self.capsules.values():
            if capsule.presence_score <= 0.1:
                continue

            # Profile/model scope filtering
            if effective_scope is not None:
                capsule_scope = getattr(capsule, 'profile_scope', None) or getattr(capsule, 'model_scope', None)
                if include_shared:
                    if capsule_scope is not None and capsule_scope != effective_scope:
                        continue
                else:
                    if capsule_scope != effective_scope:
                        continue

            for phrase in capsule.cue_phrases:
                if cue_lower in phrase.lower() or phrase.lower() in cue_lower:
                    matches.append(capsule)
                    break

        # Sort by presence score, then by last accessed
        matches.sort(key=lambda c: (c.presence_score, c.last_accessed), reverse=True)

        return matches[:limit]

    # Proposal management

    def save_proposal(self, proposal: MemoryProposal) -> str:
        """Save a memory proposal."""
        if not proposal.id:
            proposal.id = str(uuid.uuid4())
        self.proposals[proposal.id] = proposal
        return proposal.id

    def get_proposal(self, proposal_id: str) -> Optional[MemoryProposal]:
        """Get a proposal by ID."""
        return self.proposals.get(proposal_id)

    def list_proposals(self, status: str = "pending") -> list[MemoryProposal]:
        """List proposals by status."""
        return [
            p for p in self.proposals.values()
            if p.status == status
        ]

    def update_proposal_status(self, proposal_id: str, status: str) -> bool:
        """Update proposal status."""
        if proposal_id not in self.proposals:
            return False
        self.proposals[proposal_id].status = status
        return True

    # Batch operations

    def update_presence_scores(self, updates: dict[str, float]) -> int:
        """Batch update presence scores."""
        count = 0
        for capsule_id, score in updates.items():
            if capsule_id in self.capsules:
                self.capsules[capsule_id].presence_score = score
                count += 1
        return count

    def get_capsules_for_decay(
        self,
        before: datetime,
        exclude_retention: list[RetentionPolicy] | None = None
    ) -> list[MemoryCapsule]:
        """Get capsules eligible for decay processing."""
        result = []

        for capsule in self.capsules.values():
            if capsule.last_accessed >= before:
                continue
            if capsule.presence_score <= 0.0:
                continue
            if exclude_retention and capsule.retention in exclude_retention:
                continue
            result.append(capsule)

        return result

    # Utility

    def count_capsules(self, filter: Optional[CapsuleFilter] = None) -> int:
        """Count capsules matching filter."""
        if filter is None:
            return len(self.capsules)
        return len(self.list_capsules(filter))

    def export_all(self) -> list[dict[str, Any]]:
        """Export all capsules as dictionaries."""
        return [c.to_dict() for c in self.capsules.values()]

    def import_capsules(self, capsules: list[dict[str, Any]]) -> int:
        """Import capsules from dictionaries."""
        count = 0
        for data in capsules:
            try:
                capsule = create_capsule(data)
                self.save_capsule(capsule)
                count += 1
            except Exception:
                pass
        return count

    # ========================================================================
    # Conversation History Operations
    # ========================================================================

    def save_conversation(self, conversation: Conversation) -> str:
        """Save a conversation to memory."""
        if not conversation.id:
            conversation.id = str(uuid.uuid4())
        self.conversations[conversation.id] = conversation
        return conversation.id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        include_archived: bool = False,
        model_scope: Optional[str] = None,
        include_shared: bool = True,
    ) -> list[Conversation]:
        """List conversations with optional filtering."""
        convs = list(self.conversations.values())

        if source:
            convs = [c for c in convs if c.source == source]

        if not include_archived:
            convs = [c for c in convs if not c.archived]

        if model_scope is not None:
            if include_shared:
                convs = [c for c in convs if getattr(c, 'model_scope', None) == model_scope or getattr(c, 'model_scope', None) is None]
            else:
                convs = [c for c in convs if getattr(c, 'model_scope', None) == model_scope]

        # Sort by updated_at descending
        convs.sort(key=lambda c: c.updated_at, reverse=True)

        return convs[offset:offset + limit]

    def update_conversation(self, conversation: Conversation) -> bool:
        """Update an existing conversation."""
        if conversation.id not in self.conversations:
            return False
        conversation.updated_at = datetime.utcnow()
        self.conversations[conversation.id] = conversation
        return True

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        if conversation_id not in self.conversations:
            return False

        # Delete associated messages
        msg_ids_to_delete = [
            m.id for m in self.messages.values()
            if m.conversation_id == conversation_id
        ]
        for msg_id in msg_ids_to_delete:
            del self.messages[msg_id]

        del self.conversations[conversation_id]
        return True

    def save_message(self, message: Message) -> str:
        """Save a message to memory."""
        if not message.id:
            message.id = str(uuid.uuid4())
        self.messages[message.id] = message
        return message.id

    def save_messages_batch(self, messages: list[Message]) -> int:
        """Save multiple messages in a batch."""
        count = 0
        for msg in messages:
            if not msg.id:
                msg.id = str(uuid.uuid4())
            self.messages[msg.id] = msg
            count += 1
        return count

    def get_message(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        return self.messages.get(message_id)

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a conversation."""
        msgs = [
            m for m in self.messages.values()
            if m.conversation_id == conversation_id
        ]

        # Sort by timestamp
        msgs.sort(key=lambda m: m.timestamp)

        return msgs[offset:offset + limit]

    def search_messages(
        self,
        query: str,
        limit: int = 20,
        source: Optional[str] = None,
    ) -> list[MessageSearchResult]:
        """Full-text search across all messages."""
        query_lower = query.lower()
        results = []

        for msg in self.messages.values():
            if source and msg.source != source:
                continue

            if query_lower in msg.content.lower():
                conv = self.conversations.get(msg.conversation_id)
                conv_name = conv.name if conv else ""

                results.append(MessageSearchResult(
                    message=msg,
                    conversation_name=conv_name,
                    relevance_score=1.0,
                ))

        # Sort by timestamp descending
        results.sort(key=lambda r: r.message.timestamp, reverse=True)

        return results[:limit]

    def count_messages(self, conversation_id: Optional[str] = None) -> int:
        """Count messages, optionally for a specific conversation."""
        if conversation_id:
            return sum(
                1 for m in self.messages.values()
                if m.conversation_id == conversation_id
            )
        return len(self.messages)

    def count_conversations(self) -> int:
        """Count total conversations."""
        return len(self.conversations)

    def update_message(self, message: Message) -> bool:
        """Update an existing message."""
        if message.id not in self.messages:
            return False
        self.messages[message.id] = message
        return True

    def delete_message(self, message_id: str) -> bool:
        """Delete a single message."""
        if message_id not in self.messages:
            return False
        del self.messages[message_id]
        return True

    def delete_messages_after(self, conversation_id: str, message_id: str) -> int:
        """Delete a message and all messages after it in a conversation."""
        msg = self.messages.get(message_id)
        if not msg:
            return 0

        target_time = msg.timestamp
        msg_ids_to_delete = [
            m.id for m in self.messages.values()
            if m.conversation_id == conversation_id and m.timestamp >= target_time
        ]

        for mid in msg_ids_to_delete:
            del self.messages[mid]

        return len(msg_ids_to_delete)

    # ========================================================================
    # Profile Operations
    # ========================================================================

    def save_profile(self, profile: Profile) -> None:
        """Save a profile to memory."""
        self.profiles[profile.id] = profile

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        return self.profiles.get(profile_id)

    def update_profile(self, profile: Profile) -> None:
        """Update an existing profile."""
        if profile.id in self.profiles:
            profile.updated_at = datetime.utcnow()
            self.profiles[profile.id] = profile

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile."""
        if profile_id not in self.profiles:
            return False
        del self.profiles[profile_id]
        return True

    def list_profiles(self) -> list[Profile]:
        """List all profiles."""
        profiles = list(self.profiles.values())
        # Sort by updated_at descending
        profiles.sort(key=lambda p: p.updated_at, reverse=True)
        return profiles
