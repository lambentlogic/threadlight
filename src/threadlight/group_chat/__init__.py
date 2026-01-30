"""
Group Chat module for Threadlight.

Enables multi-profile conversations where multiple AI personas
can interact within the same conversation.

This module provides:
- GroupChat: Container for multi-profile conversations
- TurnOrderStrategy: Different turn-taking strategies
- GroupChatManager: Orchestrates group conversations
"""

from threadlight.group_chat.models import (
    GroupChat,
    TurnOrderStrategy,
    ProfileResponse,
    GroupMessage,
)
from threadlight.group_chat.manager import GroupChatManager

__all__ = [
    "GroupChat",
    "TurnOrderStrategy",
    "ProfileResponse",
    "GroupMessage",
    "GroupChatManager",
]
