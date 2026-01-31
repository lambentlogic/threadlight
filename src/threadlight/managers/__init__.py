"""
Manager classes for Threadlight.

Each manager encapsulates a specific domain of functionality,
keeping the main Threadlight class focused on coordination.
"""

from threadlight.managers.group_chat import GroupChatManager
from threadlight.managers.profiles import ProfileInterface
from threadlight.managers.style import StyleManager
from threadlight.managers.model_config import ModelConfigManager
from threadlight.managers.memory_types import CustomTypeManager
from threadlight.managers.chat import ChatManager

__all__ = [
    "GroupChatManager",
    "ProfileInterface",
    "StyleManager",
    "ModelConfigManager",
    "CustomTypeManager",
    "ChatManager",
]
