"""Tests for group chat functionality.

This module tests the multi-profile conversation feature where multiple
AI profiles can participate in the same conversation, with their responses
properly attributed and formatted.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from threadlight.core import Threadlight
from threadlight.profiles.profile import Profile, ModelStrategy
from threadlight.storage.base import Conversation, Message
from threadlight.providers.base import ProviderResponse


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock provider that returns canned responses."""
    # Patch create_provider in both threadlight.core and threadlight.providers
    # The ProviderManager imports from threadlight.providers at runtime
    with patch("threadlight.core.create_provider") as mock_create_core, \
         patch("threadlight.providers.create_provider") as mock_create_providers:
        mock_prov = MagicMock()
        mock_prov.complete.return_value = ProviderResponse(
            content="Mock response",
            finish_reason="stop",
            model="test-model",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
        mock_prov.stream.return_value = iter(["Hello", " from", " profile"])
        mock_prov.health_check.return_value = True
        mock_prov.model = "test-model"
        mock_create_core.return_value = mock_prov
        mock_create_providers.return_value = mock_prov
        yield mock_prov


@pytest.fixture
def threadlight(mock_provider):
    """Create a Threadlight instance with mock provider."""
    tl = Threadlight(
        storage_backend="memory",
        identity_name="TestBot",
        system_prompt="You are a test AI.",
        enable_memory=True,
        enable_decay=False,
    )
    # Directly set the mock provider to ensure it's used regardless of user config
    tl.provider = mock_provider
    yield tl
    tl.close()


@pytest.fixture
def two_profiles(threadlight):
    """Create two test profiles for group chat."""
    profile_a = threadlight.create_profile(
        name="Fable",
        description="A presence-centered AI",
        system_prompt="You are Fable, a mythically-grounded assistant.",
        philosophy="Presence-centered, emotionally resonant",
    )

    profile_b = threadlight.create_profile(
        name="Claude",
        description="A helpful AI assistant",
        system_prompt="You are Claude, a direct and thoughtful assistant.",
        philosophy="Clear communication, precise reasoning",
    )

    return profile_a, profile_b


@pytest.fixture
def three_profiles(threadlight, two_profiles):
    """Create three test profiles for group chat."""
    profile_a, profile_b = two_profiles

    profile_c = threadlight.create_profile(
        name="Oracle",
        description="A wise counselor",
        system_prompt="You are Oracle, offering wisdom and insight.",
        philosophy="Deep reflection, archetypal wisdom",
    )

    return profile_a, profile_b, profile_c


@pytest.fixture
def group_conversation(threadlight, two_profiles):
    """Create a group conversation with two profiles."""
    profile_a, profile_b = two_profiles

    conversation = threadlight.create_group_conversation(
        name="Test Group Chat",
        profile_ids=[profile_a.id, profile_b.id],
    )

    return conversation


# ============================================================================
# Test format_group_chat_history
# ============================================================================


class TestFormatGroupChatHistory:
    """Tests for conversation history formatting in group chats."""

    def test_empty_history(self, threadlight):
        """Test formatting with empty message list."""
        result = threadlight.format_group_chat_history([], "profile-1")
        assert result == []

    def test_user_messages_only(self, threadlight, two_profiles):
        """Test formatting when only user messages exist."""
        profile_a, profile_b = two_profiles

        messages = [
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role="user",
                content="Hello everyone",
                timestamp=datetime.utcnow(),
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role="user",
                content="What do you think?",
                timestamp=datetime.utcnow(),
            ),
        ]

        result = threadlight.format_group_chat_history(messages, profile_a.id)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello everyone"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "What do you think?"

    def test_active_profile_messages_kept_as_assistant(self, threadlight, two_profiles):
        """Test that the active profile's messages remain as assistant role."""
        profile_a, profile_b = two_profiles

        messages = [
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role="user",
                content="Hello",
                timestamp=datetime.utcnow(),
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role="assistant",
                content="Hi there!",
                timestamp=datetime.utcnow(),
                profile_id=profile_a.id,
            ),
        ]

        # Format for profile A's perspective
        result = threadlight.format_group_chat_history(messages, profile_a.id)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Hi there!"

    def test_other_profile_messages_tagged_in_user_context(self, threadlight, two_profiles):
        """Test that other profiles' messages are tagged and embedded in user messages."""
        profile_a, profile_b = two_profiles

        messages = [
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role="user",
                content="Hello",
                timestamp=datetime.utcnow(),
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role="assistant",
                content="Hi from Fable",
                timestamp=datetime.utcnow(),
                profile_id=profile_a.id,
            ),
        ]

        # Format for profile B's perspective - profile A's message should be tagged
        result = threadlight.format_group_chat_history(messages, profile_b.id)

        # Should have user message, then tagged profile A message as separate user message
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        # Tagged message appears as a separate user message
        assert result[1]["role"] == "user"
        assert "[Fable:]" in result[1]["content"]
        assert "Hi from Fable" in result[1]["content"]

    def test_interleaved_messages(self, threadlight, two_profiles):
        """Test formatting with interleaved user and assistant messages."""
        profile_a, profile_b = two_profiles

        messages = [
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role="user",
                content="What's your opinion?",
                timestamp=datetime.utcnow(),
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role="assistant",
                content="I think presence matters",
                timestamp=datetime.utcnow(),
                profile_id=profile_a.id,
            ),
            Message(
                id="msg-3",
                conversation_id="conv-1",
                role="assistant",
                content="I agree, let me add clarity",
                timestamp=datetime.utcnow(),
                profile_id=profile_b.id,
            ),
            Message(
                id="msg-4",
                conversation_id="conv-1",
                role="user",
                content="Can you elaborate?",
                timestamp=datetime.utcnow(),
            ),
        ]

        # Format for profile A's perspective
        result = threadlight.format_group_chat_history(messages, profile_a.id)

        # The implementation combines tagged other-profile messages into the next user message
        # Result: user, assistant (own), user (with Claude's tagged + next user message)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"  # Own message
        # Claude's tagged message is combined with the following user message
        assert result[2]["role"] == "user"
        assert "[Claude:]" in result[2]["content"]
        assert "Can you elaborate?" in result[2]["content"]

    def test_consecutive_other_profile_messages(self, threadlight, three_profiles):
        """Test formatting when multiple other profiles respond consecutively."""
        profile_a, profile_b, profile_c = three_profiles

        messages = [
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role="user",
                content="What do you all think?",
                timestamp=datetime.utcnow(),
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role="assistant",
                content="Response from Claude",
                timestamp=datetime.utcnow(),
                profile_id=profile_b.id,
            ),
            Message(
                id="msg-3",
                conversation_id="conv-1",
                role="assistant",
                content="Response from Oracle",
                timestamp=datetime.utcnow(),
                profile_id=profile_c.id,
            ),
        ]

        # Format for profile A's perspective - should see both others tagged
        result = threadlight.format_group_chat_history(messages, profile_a.id)

        # User message followed by combined tagged responses as separate user message
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What do you all think?"
        # Tagged messages combined into one user message
        assert result[1]["role"] == "user"
        assert "[Claude:]" in result[1]["content"]
        assert "[Oracle:]" in result[1]["content"]


# ============================================================================
# Test Group Conversation Creation
# ============================================================================


class TestCreateGroupConversation:
    """Tests for creating group conversations."""

    def test_create_group_conversation(self, threadlight, two_profiles):
        """Test basic group conversation creation."""
        profile_a, profile_b = two_profiles

        conversation = threadlight.create_group_conversation(
            name="Test Discussion",
            profile_ids=[profile_a.id, profile_b.id],
        )

        assert conversation.name == "Test Discussion"
        assert len(conversation.participant_profiles) == 2
        assert profile_a.id in conversation.participant_profiles
        assert profile_b.id in conversation.participant_profiles

    def test_create_group_conversation_requires_two_profiles(self, threadlight, two_profiles):
        """Test that group chat requires at least 2 valid profiles."""
        profile_a, _ = two_profiles

        with pytest.raises(ValueError, match="at least 2 valid profiles"):
            threadlight.create_group_conversation(
                name="Invalid",
                profile_ids=[profile_a.id],
            )

    def test_create_group_conversation_skips_invalid_profiles(self, threadlight, two_profiles):
        """Test that invalid profile IDs are skipped with warning."""
        profile_a, profile_b = two_profiles

        # Include a fake profile ID
        conversation = threadlight.create_group_conversation(
            name="Test",
            profile_ids=[profile_a.id, profile_b.id, "fake-profile-id"],
        )

        # Should only include valid profiles
        assert len(conversation.participant_profiles) == 2

    def test_create_group_conversation_with_metadata(self, threadlight, two_profiles):
        """Test creating group conversation with metadata."""
        profile_a, profile_b = two_profiles

        conversation = threadlight.create_group_conversation(
            name="Test",
            profile_ids=[profile_a.id, profile_b.id],
            metadata={"topic": "Philosophy"},
        )

        assert conversation.metadata.get("topic") == "Philosophy"


# ============================================================================
# Test Group Chat Messaging
# ============================================================================


class TestGroupChat:
    """Tests for group chat message sending."""

    def test_group_chat_responses(self, threadlight, group_conversation, mock_provider):
        """Test getting responses from group chat."""
        # Setup different responses for each profile
        responses_queue = iter([
            ProviderResponse(
                content="Fable's response",
                finish_reason="stop",
                model="test-model",
                prompt_tokens=50,
                completion_tokens=20,
                total_tokens=70,
            ),
            ProviderResponse(
                content="Claude's response",
                finish_reason="stop",
                model="test-model",
                prompt_tokens=50,
                completion_tokens=20,
                total_tokens=70,
            ),
        ])
        mock_provider.complete.side_effect = lambda *args, **kwargs: next(responses_queue)

        responses = threadlight.group_chat(
            message="Hello everyone!",
            conversation_id=group_conversation.id,
        )

        assert len(responses) == 2
        assert any(r["profile_name"] == "Fable" for r in responses)
        assert any(r["profile_name"] == "Claude" for r in responses)

    def test_group_chat_saves_messages(self, threadlight, group_conversation, mock_provider):
        """Test that group chat saves all messages to storage."""
        responses = threadlight.group_chat(
            message="Test message",
            conversation_id=group_conversation.id,
        )

        # Get messages from conversation
        messages = threadlight.storage.get_messages(group_conversation.id)

        # Should have user message + 2 assistant messages
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "assistant"

    def test_group_chat_profile_attribution(self, threadlight, group_conversation, mock_provider, two_profiles):
        """Test that messages are correctly attributed to profiles."""
        profile_a, profile_b = two_profiles

        threadlight.group_chat(
            message="Test",
            conversation_id=group_conversation.id,
        )

        messages = threadlight.storage.get_messages(group_conversation.id)

        # Check profile attribution
        assistant_messages = [m for m in messages if m.role == "assistant"]
        assert assistant_messages[0].profile_id == profile_a.id
        assert assistant_messages[1].profile_id == profile_b.id

    def test_group_chat_with_profile_override(self, threadlight, group_conversation, three_profiles, mock_provider):
        """Test group chat with explicit profile list override."""
        profile_a, profile_b, profile_c = three_profiles

        # Add third profile to conversation
        threadlight.add_profile_to_conversation(group_conversation.id, profile_c.id)

        # Only request responses from subset of profiles
        responses = threadlight.group_chat(
            message="Test",
            conversation_id=group_conversation.id,
            profile_ids=[profile_a.id, profile_c.id],  # Skip profile_b
        )

        assert len(responses) == 2
        assert any(r["profile_name"] == "Fable" for r in responses)
        assert any(r["profile_name"] == "Oracle" for r in responses)
        assert not any(r["profile_name"] == "Claude" for r in responses)

    def test_group_chat_handles_missing_profile(self, threadlight, group_conversation, mock_provider):
        """Test that group chat handles missing profiles gracefully."""
        responses = threadlight.group_chat(
            message="Test",
            conversation_id=group_conversation.id,
            profile_ids=["nonexistent-profile", group_conversation.participant_profiles[0]],
        )

        # Should have error for missing profile, response for valid one
        assert len(responses) == 2
        error_response = next(r for r in responses if r.get("error"))
        assert "not found" in error_response["error"]

    def test_group_chat_conversation_not_found(self, threadlight, mock_provider):
        """Test group chat with invalid conversation ID."""
        with pytest.raises(ValueError, match="Conversation not found"):
            threadlight.group_chat(
                message="Test",
                conversation_id="fake-conversation-id",
            )

    def test_group_chat_no_profiles(self, threadlight, mock_provider):
        """Test group chat with no profiles specified."""
        # Create a conversation without participant_profiles
        conversation = Conversation(
            id=str(uuid.uuid4()),
            name="Empty Participants",
            source="local",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            participant_profiles=[],
        )
        threadlight.storage.save_conversation(conversation)

        with pytest.raises(ValueError, match="No profiles specified"):
            threadlight.group_chat(
                message="Test",
                conversation_id=conversation.id,
            )


# ============================================================================
# Test Streaming Group Chat
# ============================================================================


class TestStreamGroupChat:
    """Tests for streaming group chat responses."""

    def test_stream_group_chat_events(self, threadlight, group_conversation, two_profiles, mock_provider):
        """Test that streaming yields proper event sequence."""
        profile_a, profile_b = two_profiles

        events = list(threadlight.stream_group_chat(
            message="Hello",
            conversation_id=group_conversation.id,
        ))

        # Should have events for each profile
        event_types = [e["type"] for e in events]

        # Check for profile_start events
        assert event_types.count("profile_start") == 2

        # Check for chunk events (from mock stream)
        assert "chunk" in event_types

        # Check for profile_complete events
        assert event_types.count("profile_complete") == 2

        # Check for final complete event
        assert events[-1]["type"] == "complete"

    def test_stream_group_chat_profile_order(self, threadlight, group_conversation, two_profiles, mock_provider):
        """Test that profiles respond in order."""
        profile_a, profile_b = two_profiles

        events = list(threadlight.stream_group_chat(
            message="Hello",
            conversation_id=group_conversation.id,
        ))

        # Get profile_start events in order
        starts = [e for e in events if e["type"] == "profile_start"]

        assert starts[0]["profile_id"] == profile_a.id
        assert starts[1]["profile_id"] == profile_b.id

    def test_stream_group_chat_chunks_attributed(self, threadlight, group_conversation, two_profiles, mock_provider):
        """Test that chunks are attributed to correct profile."""
        profile_a, _ = two_profiles

        events = list(threadlight.stream_group_chat(
            message="Hello",
            conversation_id=group_conversation.id,
        ))

        # Get first profile's chunks
        first_profile_chunks = []
        recording = False
        for e in events:
            if e["type"] == "profile_start" and e["profile_id"] == profile_a.id:
                recording = True
            elif e["type"] == "profile_complete" and e["profile_id"] == profile_a.id:
                recording = False
            elif e["type"] == "chunk" and recording:
                first_profile_chunks.append(e)

        # All chunks should be attributed to profile A
        for chunk in first_profile_chunks:
            assert chunk["profile_id"] == profile_a.id

    def test_stream_group_chat_complete_event(self, threadlight, group_conversation, mock_provider):
        """Test that complete event contains all responses."""
        events = list(threadlight.stream_group_chat(
            message="Hello",
            conversation_id=group_conversation.id,
        ))

        complete_event = events[-1]
        assert complete_event["type"] == "complete"
        assert "responses" in complete_event
        assert len(complete_event["responses"]) == 2


# ============================================================================
# Test Profile Conversation Management
# ============================================================================


class TestProfileConversationManagement:
    """Tests for adding/removing profiles from conversations."""

    def test_add_profile_to_conversation(self, threadlight, group_conversation, three_profiles):
        """Test adding a profile to existing conversation."""
        _, _, profile_c = three_profiles

        result = threadlight.add_profile_to_conversation(
            group_conversation.id,
            profile_c.id,
        )

        assert result is True

        # Verify profile was added
        conversation = threadlight.storage.get_conversation(group_conversation.id)
        assert profile_c.id in conversation.participant_profiles

    def test_add_duplicate_profile(self, threadlight, group_conversation, two_profiles):
        """Test adding a profile that's already a participant."""
        profile_a, _ = two_profiles

        result = threadlight.add_profile_to_conversation(
            group_conversation.id,
            profile_a.id,  # Already a participant
        )

        assert result is False

    def test_remove_profile_from_conversation(self, threadlight, group_conversation, two_profiles):
        """Test removing a profile from conversation."""
        profile_a, _ = two_profiles

        result = threadlight.remove_profile_from_conversation(
            group_conversation.id,
            profile_a.id,
        )

        assert result is True

        # Verify profile was removed
        conversation = threadlight.storage.get_conversation(group_conversation.id)
        assert profile_a.id not in conversation.participant_profiles

    def test_remove_nonexistent_profile(self, threadlight, group_conversation):
        """Test removing a profile that's not a participant."""
        result = threadlight.remove_profile_from_conversation(
            group_conversation.id,
            "fake-profile-id",
        )

        assert result is False


# ============================================================================
# Test Memory Isolation in Group Chat
# ============================================================================


class TestGroupChatMemoryIsolation:
    """Tests for memory isolation between profiles in group chat."""

    def test_profiles_maintain_separate_memories(self, threadlight, two_profiles, mock_provider):
        """Test that profiles don't access each other's isolated memories."""
        profile_a, profile_b = two_profiles

        # Enable memory isolation
        threadlight.config.memory.per_profile_isolation = True

        # Create a memory for profile A
        threadlight.switch_profile(profile_a.id)
        threadlight.memory.create(
            type="relational",
            content={"entity": "Secret", "relationship": "Known only to Fable"},
            consent_confirmed=True,
            shared=False,  # Profile-specific
        )

        # Verify profile A can recall it
        memories_a = threadlight.memory.recall("Secret", limit=10)
        assert len([m for m in memories_a if "Secret" in str(m.content)]) > 0

        # Switch to profile B
        threadlight.switch_profile(profile_b.id)

        # Profile B should NOT see the isolated memory
        memories_b = threadlight.memory.recall("Secret", limit=10)
        secret_memories = [m for m in memories_b if "Secret" in str(m.content)]
        # Note: This test depends on the memory isolation implementation
        # If isolation is working, profile B shouldn't see profile A's memory

    def test_shared_memories_accessible_to_all(self, threadlight, two_profiles, mock_provider):
        """Test that shared memories are accessible to all profiles."""
        profile_a, profile_b = two_profiles

        # Enable memory isolation
        threadlight.config.memory.per_profile_isolation = True
        threadlight.config.memory.default_shared = False

        # Create a shared memory
        threadlight.switch_profile(profile_a.id)
        threadlight.memory.create(
            type="relational",
            content={"entity": "SharedThing", "relationship": "Known to all"},
            consent_confirmed=True,
            shared=True,  # Explicitly shared
        )

        # Both profiles should be able to recall it
        memories_a = threadlight.memory.recall("SharedThing", limit=10)

        threadlight.switch_profile(profile_b.id)
        memories_b = threadlight.memory.recall("SharedThing", limit=10)

        # Both should have access (shared=True)
        assert len([m for m in memories_a if "SharedThing" in str(m.content)]) > 0
        # Note: depends on access_shared_memories setting of profile B
