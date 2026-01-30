"""
GroupChatManager for orchestrating multi-profile conversations.

This module manages the flow of group conversations, handling:
- Turn order and speaker selection
- Profile context injection
- Response aggregation
- Conversation state management
"""

from typing import Optional, Iterator, Any
import re
import logging

from threadlight.group_chat.models import (
    GroupChat,
    TurnOrderStrategy,
    ProfileResponse,
    GroupMessage,
)

logger = logging.getLogger(__name__)


class GroupChatManager:
    """
    Manages group chat conversations with multiple profiles.

    The GroupChatManager orchestrates conversations between multiple AI
    profiles, handling turn order, context building, and response generation.

    Example:
        manager = GroupChatManager(threadlight)
        group = manager.create_group(
            name="Debate",
            profile_ids=["profile-a", "profile-b"],
            turn_strategy=TurnOrderStrategy.DEBATE,
        )
        responses = manager.send_message(group.id, "What are your thoughts on AI?")
    """

    def __init__(self, threadlight: Any):
        """
        Initialize the GroupChatManager.

        Args:
            threadlight: The Threadlight instance to use for inference
        """
        self.tl = threadlight
        self._groups: dict[str, GroupChat] = {}

    def create_group(
        self,
        name: str,
        profile_ids: list[str],
        turn_strategy: TurnOrderStrategy = TurnOrderStrategy.SEQUENTIAL,
        description: str = "",
        moderator_profile_id: Optional[str] = None,
    ) -> GroupChat:
        """
        Create a new group chat.

        Args:
            name: Display name for the group
            profile_ids: List of profile IDs to include
            turn_strategy: How to determine speaking order
            description: Optional description
            moderator_profile_id: Profile to moderate (for MODERATED strategy)

        Returns:
            The created GroupChat
        """
        group = GroupChat(
            name=name,
            description=description,
            profile_ids=profile_ids,
            turn_strategy=turn_strategy,
            moderator_profile_id=moderator_profile_id,
        )

        self._groups[group.id] = group
        logger.info(f"Created group chat: {name} with {len(profile_ids)} profiles")

        return group

    def get_group(self, group_id: str) -> Optional[GroupChat]:
        """Get a group chat by ID."""
        return self._groups.get(group_id)

    def list_groups(self) -> list[GroupChat]:
        """List all group chats."""
        return list(self._groups.values())

    def delete_group(self, group_id: str) -> bool:
        """Delete a group chat."""
        if group_id in self._groups:
            del self._groups[group_id]
            return True
        return False

    def send_message(
        self,
        group_id: str,
        message: str,
        addressed_to: Optional[str] = None,
    ) -> list[ProfileResponse]:
        """
        Send a message to a group chat and get responses.

        Args:
            group_id: The group chat ID
            message: The user's message
            addressed_to: Optional profile ID to address directly

        Returns:
            List of ProfileResponse objects from responding profiles
        """
        group = self._groups.get(group_id)
        if not group:
            raise ValueError(f"Group chat not found: {group_id}")

        # Add user message to history
        user_msg = GroupMessage(
            role="user",
            content=message,
            addressed_to=addressed_to or self._extract_addressed(message, group),
        )
        group.add_message(user_msg)

        # Get responses based on turn strategy
        responses = self._get_responses(group, message, user_msg.addressed_to)

        # Add responses to history
        for response in responses:
            if not response.passed and not response.error:
                assistant_msg = GroupMessage(
                    role="assistant",
                    content=response.content,
                    profile_id=response.profile_id,
                    profile_name=response.profile_name,
                )
                group.add_message(assistant_msg)

        return responses

    def _get_responses(
        self,
        group: GroupChat,
        message: str,
        addressed_to: Optional[str],
    ) -> list[ProfileResponse]:
        """
        Get responses from profiles based on the group's turn strategy.

        Args:
            group: The group chat
            message: The user's message
            addressed_to: Profile ID if message was addressed

        Returns:
            List of ProfileResponse objects
        """
        strategy = group.turn_strategy
        responses = []

        if strategy == TurnOrderStrategy.SEQUENTIAL:
            # One profile responds per turn
            speaker_id = group.get_next_speaker()
            if speaker_id:
                response = self._get_profile_response(group, speaker_id, message)
                responses.append(response)
                group.advance_turn()

        elif strategy == TurnOrderStrategy.PARALLEL:
            # All profiles respond
            for profile_id in group.profile_ids:
                response = self._get_profile_response(group, profile_id, message)
                responses.append(response)

        elif strategy == TurnOrderStrategy.ADDRESSED:
            # Only addressed profile responds
            if addressed_to:
                response = self._get_profile_response(group, addressed_to, message)
                responses.append(response)
            elif not group.require_addressing:
                # Fall back to sequential if not required
                speaker_id = group.get_next_speaker()
                if speaker_id:
                    response = self._get_profile_response(group, speaker_id, message)
                    responses.append(response)
                    group.advance_turn()

        elif strategy == TurnOrderStrategy.ROUND_ROBIN:
            # Next profile in order (handles passing internally)
            attempts = 0
            max_attempts = len(group.profile_ids)
            while attempts < max_attempts:
                speaker_id = group.get_next_speaker()
                if speaker_id:
                    response = self._get_profile_response(group, speaker_id, message)
                    group.advance_turn()
                    if not response.passed:
                        responses.append(response)
                        break
                    responses.append(response)
                attempts += 1

        elif strategy == TurnOrderStrategy.DEBATE:
            # Two profiles go back and forth
            if len(group.profile_ids) >= 2:
                # Get current debater
                debater_idx = group.turn_count % 2
                speaker_id = group.profile_ids[debater_idx]
                response = self._get_profile_response(
                    group, speaker_id, message, debate_mode=True
                )
                responses.append(response)
                group.advance_turn()

        elif strategy == TurnOrderStrategy.VOLUNTEER:
            # Check each profile if they want to respond
            for profile_id in group.profile_ids:
                response = self._get_profile_response(
                    group, profile_id, message, can_pass=True
                )
                if not response.passed:
                    responses.append(response)

        elif strategy == TurnOrderStrategy.MODERATED:
            # Moderator responds first, then directs conversation
            if group.moderator_profile_id:
                response = self._get_profile_response(
                    group, group.moderator_profile_id, message, is_moderator=True
                )
                responses.append(response)

        return responses

    def _get_profile_response(
        self,
        group: GroupChat,
        profile_id: str,
        message: str,
        can_pass: bool = False,
        debate_mode: bool = False,
        is_moderator: bool = False,
    ) -> ProfileResponse:
        """
        Get a response from a specific profile.

        Args:
            group: The group chat
            profile_id: Profile to get response from
            message: The message to respond to
            can_pass: Whether the profile can choose not to respond
            debate_mode: Whether this is a debate response
            is_moderator: Whether this profile is the moderator

        Returns:
            ProfileResponse with the profile's response
        """
        # Get the profile
        profile = self.tl.get_profile(profile_id)
        if not profile:
            return ProfileResponse(
                profile_id=profile_id,
                profile_name="Unknown",
                content="",
                error=f"Profile not found: {profile_id}",
            )

        try:
            # Build context for this profile
            context = self._build_profile_context(group, profile, message, debate_mode, is_moderator)

            # Switch to this profile temporarily
            original_profile = self.tl.active_profile
            self.tl.switch_profile(profile_id)

            try:
                # Get response
                history = self._build_history_for_profile(group, profile_id)
                response_text = self.tl.chat(
                    message=context,
                    history=history,
                )

                # Check if profile passed
                passed = False
                if can_pass and self._did_pass(response_text):
                    passed = True

                return ProfileResponse(
                    profile_id=profile_id,
                    profile_name=profile.name,
                    content=response_text,
                    passed=passed,
                    model_used=self.tl.provider.model,
                )

            finally:
                # Restore original profile
                if original_profile:
                    self.tl.switch_profile(original_profile.id)
                else:
                    self.tl.clear_profile()

        except Exception as e:
            logger.error(f"Error getting response from profile {profile_id}: {e}")
            return ProfileResponse(
                profile_id=profile_id,
                profile_name=profile.name if profile else "Unknown",
                content="",
                error=str(e),
            )

    def _build_profile_context(
        self,
        group: GroupChat,
        profile: Any,
        message: str,
        debate_mode: bool,
        is_moderator: bool,
    ) -> str:
        """Build context message for a profile in the group chat."""
        context_parts = []

        # Add group context
        context_parts.append(f"You are in a group conversation called '{group.name}'.")

        # List other participants
        other_profiles = [pid for pid in group.profile_ids if pid != profile.id]
        if other_profiles:
            other_names = []
            for pid in other_profiles:
                p = self.tl.get_profile(pid)
                if p:
                    other_names.append(p.name)
            if other_names:
                context_parts.append(f"Other participants: {', '.join(other_names)}")

        # Add role-specific context
        if debate_mode:
            context_parts.append(
                "This is a debate. Present your perspective clearly and engage "
                "thoughtfully with opposing viewpoints."
            )
        elif is_moderator:
            context_parts.append(
                "You are the moderator. Guide the conversation, ask follow-up questions, "
                "and ensure all participants have a chance to contribute."
            )

        context_parts.append(f"\nUser message: {message}")

        return "\n".join(context_parts)

    def _build_history_for_profile(
        self,
        group: GroupChat,
        profile_id: str,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        """Build conversation history formatted for a specific profile."""
        history = []
        messages = group.get_conversation_history(limit=limit)

        for msg in messages:
            if msg.role == "user":
                history.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Mark who said what
                if msg.profile_id == profile_id:
                    history.append({"role": "assistant", "content": msg.content})
                else:
                    # Other profile's message - show as user context
                    speaker = msg.profile_name or "Another participant"
                    history.append({
                        "role": "user",
                        "content": f"[{speaker}]: {msg.content}"
                    })

        return history

    def _extract_addressed(self, message: str, group: GroupChat) -> Optional[str]:
        """
        Extract the profile ID if the message addresses a specific profile.

        Looks for patterns like @ProfileName or direct names.
        """
        # Look for @mentions
        mention_pattern = r'@(\w+)'
        matches = re.findall(mention_pattern, message)

        for match in matches:
            # Try to find a profile with this name
            for profile_id in group.profile_ids:
                profile = self.tl.get_profile(profile_id)
                if profile and match.lower() in profile.name.lower():
                    return profile_id

        return None

    def _did_pass(self, response: str) -> bool:
        """Check if a response indicates the profile chose to pass."""
        pass_indicators = [
            "[pass]",
            "[skip]",
            "[no response]",
            "i'll pass",
            "i'll let others respond",
            "nothing to add",
        ]

        lower_response = response.lower().strip()
        return any(indicator in lower_response for indicator in pass_indicators)

    def stream_message(
        self,
        group_id: str,
        message: str,
    ) -> Iterator[tuple[str, str]]:
        """
        Stream responses from group chat profiles.

        Yields tuples of (profile_name, content_chunk).

        Note: This is a simplified implementation. Full streaming
        would require async support.
        """
        responses = self.send_message(group_id, message)

        for response in responses:
            if not response.passed and not response.error:
                # Yield profile name first
                yield (response.profile_name, "")
                # Then yield content in chunks (simulated)
                words = response.content.split()
                for word in words:
                    yield (response.profile_name, word + " ")
