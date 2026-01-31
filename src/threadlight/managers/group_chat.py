"""
Group chat management for multi-profile conversations.

This module handles all group chat functionality, including:
- Formatting message history for multi-profile context
- Sending messages to group conversations
- Streaming responses from multiple profiles
- Managing conversation participants
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, TYPE_CHECKING
import logging
import uuid
from datetime import datetime

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.profiles.profile import Profile
    from threadlight.storage.base import Conversation, Message

logger = logging.getLogger(__name__)


class GroupChatManager:
    """
    Manages group chat functionality for multi-profile conversations.

    This manager handles:
    - Formatting conversation history so each profile sees others' messages tagged
    - Coordinating responses from multiple profiles in sequence
    - Streaming responses with proper event emission
    - Adding/removing profiles from conversations
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the group chat manager.

        Args:
            threadlight: Reference to parent Threadlight instance for accessing
                        storage, profiles, and chat methods
        """
        self.tl = threadlight

    def format_history(
        self,
        messages: list['Message'],
        active_profile_id: str,
        profiles: Optional[dict[str, 'Profile']] = None,
    ) -> list[dict[str, str]]:
        """
        Format messages for multi-profile group chat.

        When prompting a specific profile, other profiles' assistant messages
        are tagged and embedded in user messages so the active profile can see
        what others said without confusion about who said what.

        Args:
            messages: List of Message objects from conversation
            active_profile_id: The profile we're currently prompting
            profiles: Optional dict mapping profile_id -> Profile for name lookup

        Returns:
            Formatted message history suitable for chat context

        Example:
            For a conversation with user, Fable, and Claude:
            - User: "what do you think?"
            - Fable (assistant): "I think presence matters"
            - Claude (assistant): "From a technical view..."

            When prompting Fable:
            - {"role": "user", "content": "what do you think?"}
            - {"role": "assistant", "content": "I think presence matters"}
            - {"role": "user", "content": "[Claude:] From a technical view..."}

            When prompting Claude:
            - {"role": "user", "content": "what do you think?\\n[Fable:] I think presence matters"}
            - {"role": "assistant", "content": "From a technical view..."}
        """
        if not messages:
            return []

        # Build profile name lookup
        profile_names: dict[str, str] = {}
        if profiles:
            for pid, p in profiles.items():
                profile_names[pid] = p.name
        else:
            # Try to look up from profile manager
            for msg in messages:
                if msg.profile_id and msg.profile_id not in profile_names:
                    profile = self.tl.get_profile(msg.profile_id)
                    if profile:
                        profile_names[msg.profile_id] = profile.name

        formatted: list[dict[str, str]] = []
        pending_other_messages: list[str] = []

        for msg in messages:
            if msg.role == "user":
                # User message - include any pending other profile messages
                content = msg.content
                if pending_other_messages:
                    # Append tagged other profile messages to user message
                    content = content + "\n" + "\n".join(pending_other_messages)
                    pending_other_messages = []
                formatted.append({"role": "user", "content": content})

            elif msg.role == "assistant":
                if msg.profile_id == active_profile_id:
                    # This profile's own message - keep as assistant
                    # First flush any pending messages as a user message
                    if pending_other_messages:
                        formatted.append({
                            "role": "user",
                            "content": "\n".join(pending_other_messages)
                        })
                        pending_other_messages = []
                    formatted.append({"role": "assistant", "content": msg.content})
                else:
                    # Other profile's message - tag it for later embedding
                    profile_name = profile_names.get(
                        msg.profile_id,
                        msg.profile_id or "Assistant"
                    )
                    tagged_content = f"[{profile_name}:] {msg.content}"
                    pending_other_messages.append(tagged_content)

            elif msg.role == "system":
                # Skip system messages in history
                continue

        # Handle any remaining pending messages
        if pending_other_messages:
            formatted.append({
                "role": "user",
                "content": "\n".join(pending_other_messages)
            })

        return formatted

    def chat(
        self,
        message: str,
        conversation_id: str,
        profile_ids: Optional[list[str]] = None,
        **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Send a message to a group chat and get responses from all participating profiles.

        Each profile responds in turn, seeing the previous profiles' responses
        tagged in the context.

        Args:
            message: User message
            conversation_id: ID of the group chat conversation
            profile_ids: Optional override of which profiles should respond
                        (defaults to conversation's participant_profiles)
            **kwargs: Additional options passed to chat()

        Returns:
            List of response dicts with profile info:
            [
                {"profile_id": "abc", "profile_name": "Fable", "content": "...", "error": None},
                {"profile_id": "def", "profile_name": "Claude", "content": "...", "error": None},
            ]

        Example:
            responses = tl.group_chat(
                message="What do you both think about AI consciousness?",
                conversation_id="conv-123",
            )
            for resp in responses:
                print(f"{resp['profile_name']}: {resp['content']}")
        """
        from threadlight.storage.base import Message

        # Get conversation
        conversation = self.tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")

        # Determine which profiles should respond
        responding_profiles = profile_ids or conversation.participant_profiles
        if not responding_profiles:
            raise ValueError("No profiles specified for group chat")

        # Load conversation history
        history_messages = self.tl.storage.get_messages(conversation_id, limit=50)

        # Save user message to conversation
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=message,
            timestamp=datetime.utcnow(),
            source="local",
        )
        self.tl.storage.save_message(user_message)
        history_messages.append(user_message)

        # Store original active profile
        original_profile = self.tl.active_profile

        responses: list[dict[str, Any]] = []

        try:
            for profile_id in responding_profiles:
                profile = self.tl.get_profile(profile_id)
                if not profile:
                    responses.append({
                        "profile_id": profile_id,
                        "profile_name": "Unknown",
                        "content": "",
                        "error": f"Profile not found: {profile_id}",
                    })
                    continue

                try:
                    # Switch to this profile
                    self.tl.switch_profile(profile_id)

                    # Format history for this profile
                    formatted_history = self.format_history(
                        history_messages,
                        active_profile_id=profile_id,
                    )

                    # Get response (disable auto-save, we handle it manually)
                    response = self.tl.chat(
                        message=message,
                        history=formatted_history,
                        auto_save=False,
                        **kwargs
                    )

                    # Save assistant message
                    assistant_message = Message(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=response,
                        timestamp=datetime.utcnow(),
                        source="local",
                        profile_id=profile_id,
                        model_used=self.tl.provider.model,
                    )
                    self.tl.storage.save_message(assistant_message)
                    history_messages.append(assistant_message)

                    responses.append({
                        "profile_id": profile_id,
                        "profile_name": profile.name,
                        "content": response,
                        "error": None,
                        "model_used": self.tl.provider.model,
                    })

                except Exception as e:
                    logger.error(f"Error getting response from profile {profile_id}: {e}")
                    responses.append({
                        "profile_id": profile_id,
                        "profile_name": profile.name if profile else "Unknown",
                        "content": "",
                        "error": str(e),
                    })

        finally:
            # Restore original profile
            if original_profile:
                self.tl.switch_profile(original_profile.id)
            else:
                self.tl.clear_profile()

        # Update conversation message count
        conversation.message_count = len(history_messages)
        conversation.updated_at = datetime.utcnow()
        self.tl.storage.update_conversation(conversation)

        return responses

    def create_conversation(
        self,
        name: str,
        profile_ids: list[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> 'Conversation':
        """
        Create a new group chat conversation with multiple profiles.

        Args:
            name: Conversation name
            profile_ids: List of profile IDs to participate
            metadata: Optional metadata dict

        Returns:
            The created Conversation

        Example:
            conv = tl.create_group_conversation(
                name="Philosophy Discussion",
                profile_ids=["fable-profile-id", "claude-profile-id"],
            )
        """
        from threadlight.storage.base import Conversation

        # Validate profiles exist
        valid_profiles = []
        for pid in profile_ids:
            profile = self.tl.get_profile(pid)
            if profile:
                valid_profiles.append(pid)
            else:
                logger.warning(f"Profile not found, skipping: {pid}")

        if len(valid_profiles) < 2:
            raise ValueError("Group chat requires at least 2 valid profiles")

        conversation = Conversation(
            id=str(uuid.uuid4()),
            name=name,
            source="local",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=0,
            metadata=metadata or {},
            participant_profiles=valid_profiles,
        )

        self.tl.storage.save_conversation(conversation)

        logger.info(f"Created group conversation '{name}' with {len(valid_profiles)} profiles")

        return conversation

    def add_profile(
        self,
        conversation_id: str,
        profile_id: str,
    ) -> bool:
        """
        Add a profile to an existing conversation's participants.

        Args:
            conversation_id: ID of conversation to modify
            profile_id: Profile ID to add

        Returns:
            True if added, False if already present or conversation not found
        """
        conversation = self.tl.storage.get_conversation(conversation_id)
        if not conversation:
            return False

        profile = self.tl.get_profile(profile_id)
        if not profile:
            logger.warning(f"Profile not found: {profile_id}")
            return False

        if profile_id in conversation.participant_profiles:
            return False  # Already a participant

        conversation.participant_profiles.append(profile_id)
        self.tl.storage.update_conversation(conversation)
        return True

    def remove_profile(
        self,
        conversation_id: str,
        profile_id: str,
    ) -> bool:
        """
        Remove a profile from a conversation's participants.

        Args:
            conversation_id: ID of conversation to modify
            profile_id: Profile ID to remove

        Returns:
            True if removed, False if not present or conversation not found
        """
        conversation = self.tl.storage.get_conversation(conversation_id)
        if not conversation:
            return False

        if profile_id not in conversation.participant_profiles:
            return False  # Not a participant

        conversation.participant_profiles.remove(profile_id)
        self.tl.storage.update_conversation(conversation)
        return True

    def stream(
        self,
        message: str,
        conversation_id: str,
        profile_ids: Optional[list[str]] = None,
        **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """
        Stream responses from a group chat.

        Yields events as each profile streams their response. Each profile
        responds in turn, with previous responses embedded as tagged content.

        Args:
            message: User message
            conversation_id: ID of the group chat conversation
            profile_ids: Optional override of which profiles should respond
            **kwargs: Additional options passed to stream()

        Yields:
            Events with different types:
            - {"type": "profile_start", "profile_id": "...", "profile_name": "..."}
            - {"type": "chunk", "profile_id": "...", "content": "..."}
            - {"type": "profile_complete", "profile_id": "...", "content": "..."}
            - {"type": "error", "profile_id": "...", "error": "..."}
            - {"type": "complete", "responses": [...]}

        Example:
            for event in tl.stream_group_chat(
                message="What do you think?",
                conversation_id="conv-123",
            ):
                if event["type"] == "chunk":
                    print(event["content"], end="", flush=True)
                elif event["type"] == "profile_start":
                    print(f"\\n{event['profile_name']}: ", end="")
        """
        from threadlight.storage.base import Message

        # Get conversation
        conversation = self.tl.storage.get_conversation(conversation_id)
        if not conversation:
            yield {
                "type": "error",
                "profile_id": None,
                "error": f"Conversation not found: {conversation_id}",
            }
            return

        # Determine which profiles should respond
        responding_profiles = profile_ids or conversation.participant_profiles
        if not responding_profiles:
            yield {
                "type": "error",
                "profile_id": None,
                "error": "No profiles specified for group chat",
            }
            return

        # Load conversation history
        history_messages = self.tl.storage.get_messages(conversation_id, limit=50)

        # Save user message to conversation
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=message,
            timestamp=datetime.utcnow(),
            source="local",
        )
        self.tl.storage.save_message(user_message)
        history_messages.append(user_message)

        # Store original active profile
        original_profile = self.tl.active_profile

        responses: list[dict[str, Any]] = []

        try:
            for profile_id in responding_profiles:
                profile = self.tl.get_profile(profile_id)
                if not profile:
                    error_response = {
                        "profile_id": profile_id,
                        "profile_name": "Unknown",
                        "content": "",
                        "error": f"Profile not found: {profile_id}",
                    }
                    responses.append(error_response)
                    yield {
                        "type": "error",
                        "profile_id": profile_id,
                        "error": f"Profile not found: {profile_id}",
                    }
                    continue

                try:
                    # Switch to this profile
                    self.tl.switch_profile(profile_id)

                    # Signal that this profile is starting
                    yield {
                        "type": "profile_start",
                        "profile_id": profile_id,
                        "profile_name": profile.name,
                    }

                    # Format history for this profile
                    formatted_history = self.format_history(
                        history_messages,
                        active_profile_id=profile_id,
                    )

                    # Stream the response
                    full_response = ""
                    for chunk in self.tl.stream(
                        message=message,
                        history=formatted_history,
                        **kwargs
                    ):
                        full_response += chunk
                        yield {
                            "type": "chunk",
                            "profile_id": profile_id,
                            "content": chunk,
                        }

                    # Save assistant message
                    assistant_message = Message(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_response,
                        timestamp=datetime.utcnow(),
                        source="local",
                        profile_id=profile_id,
                        model_used=self.tl.provider.model,
                    )
                    self.tl.storage.save_message(assistant_message)
                    history_messages.append(assistant_message)

                    response_data = {
                        "profile_id": profile_id,
                        "profile_name": profile.name,
                        "content": full_response,
                        "error": None,
                        "model_used": self.tl.provider.model,
                    }
                    responses.append(response_data)

                    yield {
                        "type": "profile_complete",
                        "profile_id": profile_id,
                        "profile_name": profile.name,
                        "content": full_response,
                    }

                except Exception as e:
                    logger.error(f"Error streaming from profile {profile_id}: {e}")
                    error_response = {
                        "profile_id": profile_id,
                        "profile_name": profile.name if profile else "Unknown",
                        "content": "",
                        "error": str(e),
                    }
                    responses.append(error_response)
                    yield {
                        "type": "error",
                        "profile_id": profile_id,
                        "error": str(e),
                    }

        finally:
            # Restore original profile
            if original_profile:
                self.tl.switch_profile(original_profile.id)
            else:
                self.tl.clear_profile()

        # Update conversation message count
        conversation.message_count = len(history_messages)
        conversation.updated_at = datetime.utcnow()
        self.tl.storage.update_conversation(conversation)

        # Yield final completion event
        yield {
            "type": "complete",
            "responses": responses,
        }
