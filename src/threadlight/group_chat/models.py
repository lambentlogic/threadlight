"""
Data models for Group Chat functionality.

Defines the core structures for multi-profile conversations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import uuid


class TurnOrderStrategy(str, Enum):
    """
    Strategy for determining which profile speaks next in a group chat.

    Strategies:
        SEQUENTIAL: Profiles speak in a fixed order (A, B, C, A, B, C, ...)
        PARALLEL: All profiles respond to each user message simultaneously
        ROUND_ROBIN: Similar to SEQUENTIAL but skips profiles that pass
        ADDRESSED: Only the addressed profile responds (@ProfileName)
        VOLUNTEER: Profiles can choose to respond or pass
        DEBATE: Two profiles debate a topic back and forth
        MODERATED: A designated moderator profile controls the flow
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ROUND_ROBIN = "round_robin"
    ADDRESSED = "addressed"
    VOLUNTEER = "volunteer"
    DEBATE = "debate"
    MODERATED = "moderated"


@dataclass
class GroupMessage:
    """A message in a group chat, with optional profile attribution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = ""  # "user", "assistant", "system"
    content: str = ""
    profile_id: Optional[str] = None  # Which profile sent this
    profile_name: Optional[str] = None  # Display name for attribution
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    # For addressed messages
    addressed_to: Optional[str] = None  # Profile ID this message is for

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "addressed_to": self.addressed_to,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroupMessage":
        """Deserialize from dictionary."""
        timestamp = data.get("timestamp", "")
        if isinstance(timestamp, str) and timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.utcnow()

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=data.get("role", ""),
            content=data.get("content", ""),
            profile_id=data.get("profile_id"),
            profile_name=data.get("profile_name"),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
            addressed_to=data.get("addressed_to"),
        )


@dataclass
class ProfileResponse:
    """Response from a profile in a group chat turn."""

    profile_id: str
    profile_name: str
    content: str
    passed: bool = False  # If the profile chose to pass/not respond
    model_used: Optional[str] = None
    tokens_used: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "content": self.content,
            "passed": self.passed,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }


@dataclass
class GroupChat:
    """
    A group chat containing multiple profiles.

    GroupChat manages the participant profiles, turn order, and conversation
    history for multi-profile interactions.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Group Chat"
    description: str = ""

    # Participants
    profile_ids: list[str] = field(default_factory=list)
    moderator_profile_id: Optional[str] = None  # For MODERATED strategy

    # Turn management
    turn_strategy: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL
    current_turn_index: int = 0
    turn_count: int = 0

    # Conversation history
    messages: list[GroupMessage] = field(default_factory=list)

    # Settings
    max_turns_per_response: int = 1  # How many profiles can respond per user msg
    allow_passing: bool = True  # Can profiles pass on responding
    require_addressing: bool = False  # Must user @mention to get response

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_profile(self, profile_id: str) -> None:
        """Add a profile to the group chat."""
        if profile_id not in self.profile_ids:
            self.profile_ids.append(profile_id)
            self.updated_at = datetime.utcnow()

    def remove_profile(self, profile_id: str) -> bool:
        """Remove a profile from the group chat."""
        if profile_id in self.profile_ids:
            self.profile_ids.remove(profile_id)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def add_message(self, message: GroupMessage) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def get_next_speaker(self) -> Optional[str]:
        """
        Get the profile ID of the next speaker based on turn strategy.

        Returns:
            Profile ID of the next speaker, or None if no profiles
        """
        if not self.profile_ids:
            return None

        if self.turn_strategy == TurnOrderStrategy.SEQUENTIAL:
            index = self.current_turn_index % len(self.profile_ids)
            return self.profile_ids[index]

        elif self.turn_strategy == TurnOrderStrategy.ROUND_ROBIN:
            # Same as SEQUENTIAL, but caller should handle passing
            index = self.current_turn_index % len(self.profile_ids)
            return self.profile_ids[index]

        elif self.turn_strategy == TurnOrderStrategy.MODERATED:
            return self.moderator_profile_id

        elif self.turn_strategy in (
            TurnOrderStrategy.PARALLEL,
            TurnOrderStrategy.ADDRESSED,
            TurnOrderStrategy.VOLUNTEER,
        ):
            # These strategies determine speakers differently
            return None

        return self.profile_ids[0] if self.profile_ids else None

    def advance_turn(self) -> None:
        """Advance to the next turn."""
        self.current_turn_index += 1
        self.turn_count += 1
        self.updated_at = datetime.utcnow()

    def get_conversation_history(
        self,
        limit: int = 50,
        include_system: bool = False,
    ) -> list[GroupMessage]:
        """
        Get conversation history.

        Args:
            limit: Maximum messages to return
            include_system: Include system messages

        Returns:
            List of messages in chronological order
        """
        messages = self.messages[-limit:]
        if not include_system:
            messages = [m for m in messages if m.role != "system"]
        return messages

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "profile_ids": self.profile_ids,
            "moderator_profile_id": self.moderator_profile_id,
            "turn_strategy": self.turn_strategy.value,
            "current_turn_index": self.current_turn_index,
            "turn_count": self.turn_count,
            "messages": [m.to_dict() for m in self.messages],
            "max_turns_per_response": self.max_turns_per_response,
            "allow_passing": self.allow_passing,
            "require_addressing": self.require_addressing,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroupChat":
        """Deserialize from dictionary."""

        def parse_datetime(val):
            if isinstance(val, datetime):
                return val
            if isinstance(val, str) and val:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return datetime.utcnow()

        messages = [
            GroupMessage.from_dict(m)
            for m in data.get("messages", [])
        ]

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Group Chat"),
            description=data.get("description", ""),
            profile_ids=data.get("profile_ids", []),
            moderator_profile_id=data.get("moderator_profile_id"),
            turn_strategy=TurnOrderStrategy(data.get("turn_strategy", "sequential")),
            current_turn_index=data.get("current_turn_index", 0),
            turn_count=data.get("turn_count", 0),
            messages=messages,
            max_turns_per_response=data.get("max_turns_per_response", 1),
            allow_passing=data.get("allow_passing", True),
            require_addressing=data.get("require_addressing", False),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
        )
