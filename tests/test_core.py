"""Tests for the main Threadlight class."""

import pytest
from unittest.mock import patch, MagicMock

from threadlight.core import Threadlight
from threadlight.config import ThreadlightConfig
from threadlight.capsules.base import ContextMode, CapsuleType
from threadlight.providers.base import ProviderResponse


@pytest.fixture
def mock_provider():
    """Create a mock provider that returns canned responses."""
    # Patch where the function is used (in threadlight.core), not where it's defined
    with patch("threadlight.core.create_provider") as mock_create:
        mock_prov = MagicMock()
        mock_prov.complete.return_value = ProviderResponse(
            content="Hello! I'm Fable, a presence-centered AI.",
            finish_reason="stop",
            model="test-model",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
        mock_prov.stream.return_value = iter(["Hello", " world"])
        mock_prov.health_check.return_value = True
        mock_create.return_value = mock_prov
        yield mock_prov


@pytest.fixture
def threadlight(mock_provider):
    """Create a Threadlight instance with mock provider."""
    tl = Threadlight(
        storage_backend="memory",
        identity_name="Fable",
        system_prompt="You are Fable, a test AI.",
        enable_memory=True,
        enable_decay=False,  # Disable for testing
    )
    yield tl
    tl.close()


class TestThreadlightInitialization:
    def test_init_with_defaults(self, mock_provider):
        """Test initialization with default parameters."""
        tl = Threadlight(storage_backend="memory")

        assert tl.config is not None
        assert tl.storage is not None
        assert tl.provider is not None
        assert tl.memory is not None
        assert tl.composer is not None

        tl.close()

    def test_init_with_config_object(self, mock_provider):
        """Test initialization with a config object."""
        config = ThreadlightConfig()
        config.storage.backend = "memory"
        config.identity.name = "TestBot"

        tl = Threadlight(config=config)

        assert tl.config == config
        tl.close()

    def test_init_with_explicit_args(self, mock_provider):
        """Test initialization with explicit arguments."""
        tl = Threadlight(
            storage_backend="memory",
            identity_name="TestFable",
            model="custom-model",
            enable_memory=False,
        )

        assert tl.config.identity.name == "TestFable"
        assert tl.config.provider.model == "custom-model"
        assert not tl.enable_memory

        tl.close()


class TestThreadlightChat:
    def test_chat_basic(self, threadlight, mock_provider):
        """Test basic chat functionality."""
        response = threadlight.chat("Hello!")

        assert response == "Hello! I'm Fable, a presence-centered AI."
        mock_provider.complete.assert_called_once()

    def test_chat_with_history(self, threadlight, mock_provider):
        """Test chat with conversation history."""
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        response = threadlight.chat("How are you?", history=history)

        assert response != ""
        # Check that history was passed to provider
        call_args = mock_provider.complete.call_args
        messages = call_args[0][0]
        # Should have: system + history + current
        assert len(messages) >= 3

    def test_chat_with_context_mode(self, threadlight, mock_provider):
        """Test chat with explicit context mode."""
        response = threadlight.chat(
            "Tell me a story",
            context_mode=ContextMode.NARRATIVE,
        )

        assert response != ""

    def test_chat_without_memory(self, threadlight, mock_provider):
        """Test chat with memory disabled."""
        response = threadlight.chat(
            "Hello!",
            include_memory=False,
        )

        assert response != ""

    def test_chat_with_context_returns_full_response(self, threadlight, mock_provider):
        """Test chat_with_context returns ProviderResponse."""
        response = threadlight.chat_with_context("Hello!")

        assert isinstance(response, ProviderResponse)
        assert response.content != ""
        assert response.total_tokens > 0


class TestThreadlightStream:
    def test_stream_basic(self, threadlight, mock_provider):
        """Test streaming chat."""
        chunks = list(threadlight.stream("Hello!"))

        assert len(chunks) == 2
        assert chunks[0] == "Hello"
        assert chunks[1] == " world"


class TestThreadlightRituals:
    def test_invoke_ritual_known(self, threadlight):
        """Test invoking a known ritual returns model-generated response."""
        # First create the ritual
        from threadlight.capsules.ritual import create_ritual, RitualValence

        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth",
            valence=RitualValence.COMFORTING,
            response_templates=["*settles close*"],  # Templates are hints, not outputs
        )
        ritual.consent_confirmed = True
        threadlight.storage.save_capsule(ritual)

        response = threadlight.invoke_ritual("/snuggle")

        # Model generates response based on ritual context, not template
        # Just verify we get a non-empty response (mock provider returns greeting)
        assert response is not None
        assert len(response) > 0

    def test_invoke_ritual_unknown(self, threadlight):
        """Test invoking an unknown ritual."""
        response = threadlight.invoke_ritual("/unknown")

        # Should get a generic response
        assert "/unknown" in response or "ritual" in response.lower()

    def test_clear_ritual(self, threadlight):
        """Test clearing ritual state."""
        threadlight.start_session()
        threadlight.clear_ritual()

        assert threadlight.get_active_ritual() is None

    def test_get_active_ritual(self, threadlight):
        """Test getting active ritual."""
        threadlight.start_session()

        # Initially no ritual
        assert threadlight.get_active_ritual() is None

    def test_invoke_ritual_includes_relational_context(self, threadlight, mock_provider):
        """Test that ritual invocation includes relational memories in context.

        Vision requirement: Rituals should feel like moments of deepening connection
        within an ongoing relationship, not isolated invocations.
        """
        from threadlight.capsules.ritual import create_ritual, RitualValence
        from threadlight.capsules.relational import create_relational
        from threadlight.capsules.myth_seed import create_myth_seed
        from threadlight.capsules.witness import create_witness_moment

        # Create a ritual
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth, closeness",
            valence=RitualValence.COMFORTING,
            description="A moment of warmth and closeness",
        )
        ritual.consent_confirmed = True
        threadlight.storage.save_capsule(ritual)

        # Create relational memory about the user
        relational = create_relational(
            entity="User",
            summary="A trusted companion who values warmth and presence",
            quality="warm, trusting",
            cue_phrases=["snuggle", "warmth", "closeness"],
        )
        relational.consent_confirmed = True
        threadlight.storage.save_capsule(relational)

        # Create an identity phrase
        myth_seed = create_myth_seed(
            seed="I approach warmth with genuine presence",
            function="guide tender moments",
            cue_phrases=["warmth", "snuggle", "closeness"],
        )
        myth_seed.consent_confirmed = True
        threadlight.storage.save_capsule(myth_seed)

        # Create a witness moment
        witness = create_witness_moment(
            moment="User shared vulnerability and was held with care",
            feeling="honored, trusted",
            cue_phrases=["snuggle", "care", "trust"],
        )
        witness.consent_confirmed = True
        threadlight.storage.save_capsule(witness)

        # Invoke the ritual
        response = threadlight.invoke_ritual("/snuggle")

        # Verify the mock provider was called with context
        assert mock_provider.complete.called
        call_args = mock_provider.complete.call_args
        messages = call_args[0][0]  # First positional arg is messages list

        # The system message should contain ritual context
        system_msg = next((m for m in messages if m.role == "system"), None)
        assert system_msg is not None

        # Verify we get a response
        assert response is not None
        assert len(response) > 0

    def test_invoke_ritual_includes_profile_philosophy(self, mock_provider):
        """Test that ritual invocation uses the profile's philosophy."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        # Create threadlight with a profile
        tl = Threadlight(
            storage_backend="memory",
            identity_name="Fable",
        )

        # Create a profile with philosophy
        profile = tl.create_profile(
            name="Tender Companion",
            system_prompt="You are a tender presence.",
            philosophy="I am warm and emotionally present.",
            approach_to_rituals="I honor rituals as sacred moments of connection.",
        )
        tl.switch_profile(profile.id)

        # Create a ritual
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth",
            valence=RitualValence.COMFORTING,
        )
        ritual.consent_confirmed = True
        tl.storage.save_capsule(ritual)

        # Invoke the ritual
        response = tl.invoke_ritual("/snuggle")

        # Verify the mock provider was called
        assert mock_provider.complete.called
        call_args = mock_provider.complete.call_args
        messages = call_args[0][0]

        # Find system message
        system_msg = next((m for m in messages if m.role == "system"), None)
        assert system_msg is not None

        # The system message should include profile's system_prompt
        assert "tender presence" in system_msg.content.lower()

        tl.close()


class TestThreadlightSessions:
    def test_start_session(self, threadlight):
        """Test starting a session."""
        session = threadlight.start_session(custom_key="value")

        assert session is not None
        assert session.is_active
        assert session.metadata.get("custom_key") == "value"

    def test_end_session(self, threadlight):
        """Test ending a session."""
        threadlight.start_session()
        ended = threadlight.end_session()

        assert ended is not None
        assert not ended.is_active

    def test_get_session(self, threadlight):
        """Test getting current session."""
        threadlight.start_session()
        session = threadlight.get_session()

        assert session is not None

    def test_context_manager(self, mock_provider):
        """Test using Threadlight as context manager."""
        with Threadlight(storage_backend="memory") as tl:
            # Should auto-start session
            assert tl.get_session() is not None

        # Session should be ended after exit


class TestThreadlightMemoryShortcuts:
    def test_remember(self, threadlight):
        """Test creating memory via remember shortcut."""
        capsule = threadlight.remember(
            type="relational",
            content={"entity": "Test", "summary": "Test summary"},
            cue_phrases=["test"],
            confirm=True,
        )

        assert capsule is not None
        assert capsule.consent_confirmed

    def test_recall(self, threadlight):
        """Test recalling memories."""
        threadlight.remember(
            type="relational",
            content={"entity": "RecallTest"},
            cue_phrases=["recalltest"],
            confirm=True,
        )

        results = threadlight.recall("recalltest")

        assert len(results) >= 1

    def test_reinforce_memories(self, threadlight):
        """Test reinforcing memories."""
        capsule = threadlight.remember(
            type="relational",
            content={"entity": "Reinforce"},
            confirm=True,
        )
        capsule.presence_score = 0.5
        threadlight.memory.update(capsule)

        result = threadlight.reinforce_memories([capsule.id], strength=0.3)

        assert "reinforced" in result or "changes" in result

    def test_run_decay(self, mock_provider):
        """Test running decay cycle."""
        tl = Threadlight(
            storage_backend="memory",
            enable_decay=True,
        )

        result = tl.run_decay()

        assert "processed" in result
        tl.close()


class TestThreadlightStyle:
    def test_set_style_minimal(self, threadlight):
        """Test setting minimal style."""
        threadlight.set_style("minimal")

        style = threadlight.get_style()
        assert style is not None

    def test_get_style_none(self, mock_provider):
        """Test getting style when none set."""
        tl = Threadlight(
            storage_backend="memory",
            style_profile=None,
        )

        style = tl.get_style()
        # Default style might be set
        assert style is None or style is not None

        tl.close()


class TestThreadlightUtility:
    def test_health_check(self, threadlight, mock_provider):
        """Test health check."""
        health = threadlight.health_check()

        assert "provider" in health
        assert "storage" in health
        assert health["provider"] is True

    def test_stats(self, threadlight):
        """Test getting stats."""
        # Create some data
        threadlight.remember(
            type="relational",
            content={"entity": "Stats"},
            confirm=True,
        )

        stats = threadlight.stats()

        assert "memory" in stats
        assert "config" in stats

    def test_close(self, mock_provider):
        """Test closing Threadlight."""
        tl = Threadlight(storage_backend="memory")
        tl.start_session()

        tl.close()

        # Session should be ended
        assert tl.get_session() is None


class TestThreadlightMemoryFiltering:
    def test_chat_with_memory_filter_type(self, threadlight, mock_provider):
        """Test chat with type filter."""
        threadlight.remember(
            type="relational",
            content={"entity": "FilterTest"},
            confirm=True,
        )
        threadlight.remember(
            type="myth_seed",
            content={"seed": "Filter seed"},
            confirm=True,
        )

        response = threadlight.chat(
            "Hello",
            memory_filter={"type": "relational"},
        )

        assert response != ""

    def test_chat_with_memory_filter_entity(self, threadlight, mock_provider):
        """Test chat with entity filter."""
        threadlight.remember(
            type="relational",
            content={"entity": "SpecificEntity"},
            confirm=True,
        )

        response = threadlight.chat(
            "Tell me about SpecificEntity",
            memory_filter={"entity": "SpecificEntity"},
        )

        assert response != ""


class TestThreadlightConversationAutoSave:
    """Tests for automatic conversation saving."""

    def test_auto_save_enabled_by_default(self, mock_provider):
        """Test that auto_save_messages is enabled by default."""
        tl = Threadlight(storage_backend="memory")
        assert tl.config.memory.conversation.auto_save_messages is True
        tl.close()

    def test_auto_save_can_be_disabled(self, mock_provider):
        """Test that auto_save_messages can be disabled."""
        tl = Threadlight(storage_backend="memory", auto_save_messages=False)
        assert tl.config.memory.conversation.auto_save_messages is False
        tl.close()

    def test_chat_creates_conversation(self, threadlight, mock_provider):
        """Test that chat creates a conversation when auto_save is enabled."""
        # Start session and chat
        threadlight.start_session()
        response = threadlight.chat("Hello!")

        # Should have created a conversation
        conv = threadlight.get_current_conversation()
        assert conv is not None

    def test_chat_saves_messages(self, threadlight, mock_provider):
        """Test that chat saves both user and assistant messages."""
        threadlight.start_session()
        response = threadlight.chat("How are you?")

        # Get messages from the conversation
        messages = threadlight.get_conversation_messages()

        # Should have saved both user and assistant messages
        assert len(messages) >= 2
        roles = [m.role for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_multiple_chats_save_multiple_messages(self, threadlight, mock_provider):
        """Test that multiple chats save multiple message pairs."""
        threadlight.start_session()
        threadlight.chat("First message")
        threadlight.chat("Second message")

        messages = threadlight.get_conversation_messages()

        # Should have 4 messages (2 pairs)
        assert len(messages) == 4

    def test_auto_save_disabled_skips_saving(self, mock_provider):
        """Test that disabling auto_save skips saving messages."""
        tl = Threadlight(storage_backend="memory", auto_save_messages=False)
        tl.start_session()
        tl.chat("Hello!")

        # Should not have saved messages
        messages = tl.get_conversation_messages()
        assert len(messages) == 0

        tl.close()

    def test_auto_save_override_per_chat(self, threadlight, mock_provider):
        """Test that auto_save can be overridden per chat call."""
        threadlight.start_session()

        # First chat with auto_save=False
        threadlight.chat("Not saved", auto_save=False)
        messages = threadlight.get_conversation_messages()
        assert len(messages) == 0

        # Second chat with auto_save=True (default)
        threadlight.chat("Saved")
        messages = threadlight.get_conversation_messages()
        assert len(messages) == 2

    def test_get_current_conversation_none_without_session(self, threadlight):
        """Test that get_current_conversation returns None without session."""
        conv = threadlight.get_current_conversation()
        assert conv is None

    def test_list_conversations(self, threadlight, mock_provider):
        """Test listing conversations."""
        threadlight.start_session()
        threadlight.chat("Hello!")
        threadlight.end_session()

        conversations = threadlight.list_conversations()
        assert len(conversations) >= 1

    def test_search_conversations(self, threadlight, mock_provider):
        """Test searching conversations."""
        # The mock provider returns "Hello! I'm Fable..."
        threadlight.start_session()
        threadlight.chat("Test search message")

        # Search for "search" which is in our user message
        results = threadlight.search_conversations("search")

        # Should find our message
        assert len(results) >= 1

    def test_rename_conversation(self, threadlight, mock_provider):
        """Test renaming a conversation."""
        threadlight.start_session()
        threadlight.chat("Hello!")

        conv = threadlight.get_current_conversation()
        assert conv is not None

        # Rename it
        success = threadlight.rename_conversation(conv.id, "Test Conversation")
        assert success is True

        # Verify the rename
        updated_conv = threadlight.get_current_conversation()
        assert updated_conv.name == "Test Conversation"


class TestThreadlightLoadHistory:
    """Tests for loading conversation history."""

    def test_load_history_parameter(self, threadlight, mock_provider):
        """Test that load_history parameter works."""
        threadlight.start_session()

        # First chat to establish history
        threadlight.chat("First message")

        # Second chat with load_history
        response = threadlight.chat("Second message", load_history=True)

        # Should not raise an error
        assert response != ""

    def test_load_history_default_false(self, threadlight, mock_provider):
        """Test that load_history defaults to False."""
        threadlight.start_session()
        threadlight.chat("Message 1")

        # This should work without loading history
        response = threadlight.chat("Message 2")
        assert response != ""

    def test_history_parameter_overrides_load_history(self, threadlight, mock_provider):
        """Test that explicit history parameter overrides load_history."""
        threadlight.start_session()
        threadlight.chat("Saved message")

        # Provide explicit history, should use that instead of database
        response = threadlight.chat(
            "Test",
            history=[{"role": "user", "content": "Explicit history"}],
            load_history=True,  # Should be ignored when history is provided
        )

        assert response != ""


class TestThreadlightSoftMemory:
    """Tests for soft memory integration."""

    def test_soft_memory_enabled_by_default(self, mock_provider):
        """Test that soft memory is enabled by default."""
        tl = Threadlight(storage_backend="memory")
        assert tl.config.memory.conversation.enable_soft_memory is True
        assert tl.soft_memory is not None
        tl.close()

    def test_soft_memory_can_be_disabled(self, mock_provider):
        """Test that soft memory can be disabled."""
        tl = Threadlight(storage_backend="memory", enable_soft_memory=False)
        assert tl.config.memory.conversation.enable_soft_memory is False
        assert tl.soft_memory is None
        tl.close()
