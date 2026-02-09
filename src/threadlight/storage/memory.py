"""
In-memory storage backend for Threadlight.

Useful for testing and ephemeral sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
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
        self.custom_types: dict[str, dict[str, Any]] = {}
        self.builtin_customizations: dict[str, dict[str, Any]] = {}

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
        self.custom_types.clear()
        self.builtin_customizations.clear()

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
        capsule.updated_at = _utc_now()
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
            if filter.shared_only:
                capsules = [c for c in capsules if getattr(c, 'profile_scope', None) is None]
            elif filter.profile_scope is not None:
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

            # Memory tier filtering
            if filter.memory_tier is not None:
                capsules = [
                    c for c in capsules
                    if getattr(c, 'memory_tier', None) == filter.memory_tier
                ]

            # Archive filtering (default: exclude archived)
            if not filter.include_archived:
                capsules = [c for c in capsules if not getattr(c, 'archived', False)]

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
            # Default: exclude archived, sort by last_accessed, limit 100
            capsules = [c for c in capsules if not getattr(c, 'archived', False)]
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
        profile_scope: Optional[str] = None,
        include_shared: bool = True,
        # Deprecated: Use profile_scope instead
        model_scope: Optional[str] = None,
    ) -> list[Conversation]:
        """List conversations with optional filtering."""
        # Backward compatibility: fall back to model_scope if profile_scope not set
        effective_scope = profile_scope if profile_scope is not None else model_scope

        convs = list(self.conversations.values())

        if source:
            convs = [c for c in convs if c.source == source]

        if not include_archived:
            convs = [c for c in convs if not c.archived]

        if effective_scope is not None:
            if include_shared:
                convs = [c for c in convs if getattr(c, 'profile_scope', None) == effective_scope or getattr(c, 'profile_scope', None) is None]
            else:
                convs = [c for c in convs if getattr(c, 'profile_scope', None) == effective_scope]

        # Sort by updated_at descending
        convs.sort(key=lambda c: c.updated_at, reverse=True)

        return convs[offset:offset + limit]

    def update_conversation(self, conversation: Conversation) -> bool:
        """Update an existing conversation."""
        if conversation.id not in self.conversations:
            return False
        conversation.updated_at = _utc_now()
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
        """Get messages for a conversation.

        For messages that belong to a variant group, only the variant with the
        highest variant_index (most recent) is returned.
        """
        msgs = [
            m for m in self.messages.values()
            if m.conversation_id == conversation_id
        ]

        # Sort by timestamp
        msgs.sort(key=lambda m: m.timestamp)

        # For variant groups, keep only the latest variant (highest variant_index)
        seen_groups: dict[str, Message] = {}
        filtered: list[Message] = []
        for m in msgs:
            if m.variant_group_id is None:
                filtered.append(m)
            else:
                existing = seen_groups.get(m.variant_group_id)
                if existing is None or m.variant_index > existing.variant_index:
                    seen_groups[m.variant_group_id] = m

        # Re-merge variant group winners into the list in timestamp order
        result: list[Message] = []
        seen_group_ids: set[str] = set()
        for m in msgs:
            if m.variant_group_id is None:
                result.append(m)
            elif m.variant_group_id not in seen_group_ids:
                # Insert the latest variant at the position of the first variant
                result.append(seen_groups[m.variant_group_id])
                seen_group_ids.add(m.variant_group_id)

        return result[offset:offset + limit]

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
        """Delete a single message.

        If the message belongs to a variant group, all messages in that
        group are deleted to avoid leaving orphaned or incomplete groups.
        """
        msg = self.messages.get(message_id)
        if msg is None:
            return False

        if msg.variant_group_id:
            # Delete all messages in the variant group
            ids_to_delete = [
                m.id for m in self.messages.values()
                if m.variant_group_id == msg.variant_group_id
            ]
            for mid in ids_to_delete:
                del self.messages[mid]
        else:
            del self.messages[message_id]

        return True

    def get_message_variants(self, variant_group_id: str) -> list[Message]:
        """Get all messages in a variant group, ordered by variant_index."""
        variants = [
            m for m in self.messages.values()
            if m.variant_group_id == variant_group_id
        ]
        variants.sort(key=lambda m: m.variant_index)
        return variants

    def delete_messages_after(self, conversation_id: str, message_id: str) -> int:
        """Delete a message and all messages after it in a conversation.

        If any deleted message belongs to a variant group that has other
        variants outside the deletion range, those variants are also deleted
        to avoid leaving incomplete groups.
        """
        msg = self.messages.get(message_id)
        if not msg:
            return 0

        target_time = msg.timestamp

        # Find messages in the direct deletion range
        in_range_ids = set(
            m.id for m in self.messages.values()
            if m.conversation_id == conversation_id and m.timestamp >= target_time
        )

        # Find variant groups that are partially in the deletion range
        groups_in_range: set[str] = set()
        for mid in in_range_ids:
            m = self.messages[mid]
            if m.variant_group_id:
                groups_in_range.add(m.variant_group_id)

        # Add orphaned variants from those groups (variants before target_time)
        orphan_ids: set[str] = set()
        for m in self.messages.values():
            if (m.variant_group_id in groups_in_range
                    and m.id not in in_range_ids):
                orphan_ids.add(m.id)

        all_ids_to_delete = in_range_ids | orphan_ids

        for mid in all_ids_to_delete:
            del self.messages[mid]

        return len(all_ids_to_delete)

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
            profile.updated_at = _utc_now()
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

    # ========================================================================
    # Custom Type Operations
    # ========================================================================

    def save_custom_type(self, type_def: dict[str, Any]) -> str:
        """Save a custom type definition."""
        type_id = type_def["type_id"]
        self.custom_types[type_id] = type_def.copy()
        return type_id

    def get_custom_type(self, type_id: str) -> Optional[dict[str, Any]]:
        """Get a custom type definition."""
        return self.custom_types.get(type_id)

    def list_custom_types(self) -> list[dict[str, Any]]:
        """List all custom type definitions."""
        return list(self.custom_types.values())

    def update_custom_type(self, type_id: str, updates: dict[str, Any]) -> bool:
        """Update a custom type definition."""
        if type_id not in self.custom_types:
            return False
        for key, value in updates.items():
            if key != "type_id":
                self.custom_types[type_id][key] = value
        self.custom_types[type_id]["updated_at"] = _utc_now().isoformat()
        return True

    def delete_custom_type(self, type_id: str) -> bool:
        """Delete a custom type definition."""
        if type_id not in self.custom_types:
            return False
        del self.custom_types[type_id]
        return True

    # ========================================================================
    # Built-in Type Customization Operations
    # ========================================================================

    def get_builtin_customization(self, type_id: str) -> Optional[dict[str, Any]]:
        """Get customization for a built-in type."""
        return self.builtin_customizations.get(type_id)

    def save_builtin_customization(self, type_id: str, customization: dict[str, Any]) -> None:
        """Save customization for a built-in type."""
        self.builtin_customizations[type_id] = {
            "type_id": type_id,
            "is_hidden": customization.get("is_hidden", False),
            "display_name": customization.get("display_name"),
            "description": customization.get("description"),
            "fields": customization.get("fields"),
            "display_template": customization.get("display_template"),
            "icon": customization.get("icon"),
            "created_at": customization.get("created_at", _utc_now().isoformat()),
            "updated_at": _utc_now().isoformat(),
        }

    def hide_builtin_type(self, type_id: str) -> bool:
        """Mark a built-in type as hidden."""
        existing = self.builtin_customizations.get(type_id)
        if existing and existing.get("is_hidden"):
            return False  # Already hidden

        if existing:
            existing["is_hidden"] = True
            existing["updated_at"] = _utc_now().isoformat()
        else:
            self.builtin_customizations[type_id] = {
                "type_id": type_id,
                "is_hidden": True,
                "display_name": None,
                "description": None,
                "fields": None,
                "display_template": None,
                "icon": None,
                "created_at": _utc_now().isoformat(),
                "updated_at": _utc_now().isoformat(),
            }
        return True

    def restore_builtin_type(self, type_id: str) -> bool:
        """Restore a hidden built-in type."""
        existing = self.builtin_customizations.get(type_id)
        if not existing or not existing.get("is_hidden"):
            return False

        # Check if there are any other customizations
        has_customizations = (
            existing.get("display_name") is not None or
            existing.get("description") is not None or
            existing.get("fields") is not None or
            existing.get("display_template") is not None or
            existing.get("icon") is not None
        )

        if has_customizations:
            existing["is_hidden"] = False
            existing["updated_at"] = _utc_now().isoformat()
        else:
            del self.builtin_customizations[type_id]

        return True

    def list_builtin_customizations(self) -> list[dict[str, Any]]:
        """List all built-in type customizations."""
        return list(self.builtin_customizations.values())

    def list_hidden_builtin_types(self) -> list[str]:
        """List type IDs of all hidden built-in types."""
        return [
            c["type_id"] for c in self.builtin_customizations.values()
            if c.get("is_hidden")
        ]

    def delete_builtin_customization(self, type_id: str) -> bool:
        """Delete all customizations for a built-in type."""
        if type_id not in self.builtin_customizations:
            return False
        del self.builtin_customizations[type_id]
        return True
