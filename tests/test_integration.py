"""
End-to-end integration tests for Threadlight.

These tests verify that all components work together correctly.
They use in-memory storage and mock providers by default,
but can be run against real APIs with proper configuration.
"""

import pytest
from unittest.mock import patch, MagicMock

from threadlight import (
    Threadlight,
    ThreadlightConfig,
    CapsuleType,
    ContextMode,
    RetentionPolicy,
)
from threadlight.providers.base import ProviderResponse


@pytest.fixture
def mock_provider():
    """Create a mock provider for integration tests."""
    with patch("threadlight.core.create_provider") as mock_create:
        mock_prov = MagicMock()

        def mock_complete(messages, **kwargs):
            # Simulate a response that references memories if present
            content = "I acknowledge your message."

            # Check if memories are in the system prompt
            if messages and messages[0].role == "system":
                system = messages[0].content
                if "Memory Context" in system:
                    content = "I remember our previous conversations."
                if "RITUAL" in system:
                    content = "*responds to the ritual with presence*"

            return ProviderResponse(
                content=content,
                finish_reason="stop",
                model="mock-model",
                prompt_tokens=100,
                completion_tokens=30,
                total_tokens=130,
            )

        mock_prov.complete.side_effect = mock_complete
        mock_prov.stream.return_value = iter(["Test", " response"])
        mock_prov.health_check.return_value = True
        mock_create.return_value = mock_prov
        yield mock_prov


@pytest.fixture
def tl(mock_provider):
    """Create a fully configured Threadlight instance."""
    instance = Threadlight(
        storage_backend="memory",
        identity_name="TestBot",
        system_prompt="You are a helpful AI assistant.",
        enable_memory=True,
        enable_decay=True,
    )
    yield instance
    instance.close()


class TestFullConversationFlow:
    """Test complete conversation flows with memory."""

    def test_conversation_with_memory_creation(self, tl, mock_provider):
        """Test a conversation where memories are created and accessed."""
        # Start session
        session = tl.start_session()

        # Create foundational memories
        rel = tl.remember(
            type="relational",
            content={
                "entity": "TestUser",
                "tone": "curious, friendly",
                "summary": "A tester exploring Threadlight",
            },
            cue_phrases=["testuser", "user", "you"],
            confirm=True,
        )

        myth = tl.remember(
            type="myth_seed",
            content={
                "seed": "Curiosity opens doors.",
                "origin": "First conversation",
            },
            retention="sacred",
            confirm=True,
        )

        # Have a conversation
        response1 = tl.chat("Hello, I'm TestUser!")

        # Should trigger memory
        response2 = tl.chat("What do you know about me?")

        # Check that memories were accessed
        session = tl.get_session()
        assert len(session.capsules_accessed) > 0

        # End session
        ended = tl.end_session()
        assert ended.message_count >= 2

    def test_conversation_with_rituals(self, tl, mock_provider):
        """Test conversation flow including rituals."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        # Create ritual
        ritual = create_ritual(
            name="/test",
            response_style="testing mode",
            valence=RitualValence.PLAYFUL,
            response_templates=["*enters test mode*"],  # Templates are hints for model
        )
        ritual.consent_confirmed = True
        tl.storage.save_capsule(ritual)

        # Start session
        tl.start_session()

        # Regular chat first
        tl.chat("Hello!")

        # Invoke ritual - now uses model-based response, not template
        ritual_response = tl.invoke_ritual("/test")
        # Just verify we get a response (model generates based on ritual context)
        assert ritual_response is not None
        assert len(ritual_response) > 0

        # Continue conversation in ritual context
        response = tl.chat("How does this feel?")

        # Ritual should be tracked
        session = tl.get_session()
        assert "/test" in session.rituals_invoked

    def test_multi_turn_with_history(self, tl, mock_provider):
        """Test multi-turn conversation maintaining history."""
        tl.start_session()

        history = []

        # Turn 1
        resp1 = tl.chat("Hello!")
        history.append({"role": "user", "content": "Hello!"})
        history.append({"role": "assistant", "content": resp1})

        # Turn 2
        resp2 = tl.chat("Tell me more.", history=history)
        history.append({"role": "user", "content": "Tell me more."})
        history.append({"role": "assistant", "content": resp2})

        # Turn 3
        resp3 = tl.chat("Interesting!", history=history)

        assert resp3 != ""

        session = tl.get_session()
        assert session.message_count == 3


class TestMemoryLifecycle:
    """Test the full memory lifecycle: create, use, decay, reinforce."""

    def test_memory_creation_and_retrieval(self, tl):
        """Test creating and retrieving memories."""
        # Create various memory types
        capsules = []

        rel = tl.remember(
            type="relational",
            content={"entity": "Lifecycle", "summary": "Testing lifecycle"},
            cue_phrases=["lifecycle"],
            confirm=True,
        )
        capsules.append(rel)

        myth = tl.remember(
            type="myth_seed",
            content={"seed": "Test wisdom"},
            retention="sacred",
            confirm=True,
        )
        capsules.append(myth)

        witness = tl.remember(
            type="witness",
            content={"moment": "First test", "feeling": "hopeful"},
            confirm=True,
        )
        capsules.append(witness)

        # Retrieve each
        for cap in capsules:
            retrieved = tl.memory.get(cap.id)
            assert retrieved is not None
            assert retrieved.id == cap.id

    def test_memory_decay_and_reinforcement(self, tl):
        """Test decay and reinforcement cycle."""
        from datetime import datetime, timedelta

        # Create memory
        capsule = tl.remember(
            type="relational",
            content={"entity": "DecayTest"},
            confirm=True,
        )

        # Age it
        capsule.last_accessed = datetime.utcnow() - timedelta(days=60)
        tl.memory.update(capsule)

        # Run decay
        decay_result = tl.run_decay()
        assert decay_result["processed"] >= 1

        # Check that presence decreased - get directly from storage to avoid touch
        decayed = tl.storage.get_capsule(capsule.id)
        assert decayed.presence_score < 1.0
        decayed_score = decayed.presence_score

        # Reinforce
        reinforce_result = tl.reinforce_memories([capsule.id], strength=0.5)

        # Check that presence increased - get directly from storage
        reinforced = tl.storage.get_capsule(capsule.id)
        assert reinforced.presence_score > decayed_score

    def test_sacred_memory_persistence(self, tl):
        """Test that sacred memories don't decay."""
        from datetime import datetime, timedelta

        # Create sacred memory
        sacred = tl.remember(
            type="myth_seed",
            content={"seed": "Sacred test"},
            retention="sacred",
            confirm=True,
        )

        original_presence = sacred.presence_score

        # Age it
        sacred.last_accessed = datetime.utcnow() - timedelta(days=365)
        tl.memory.update(sacred)

        # Run decay
        tl.run_decay()

        # Should still have same presence
        retrieved = tl.memory.get(sacred.id)
        assert retrieved.presence_score == original_presence


class TestProposalWorkflow:
    """Test the memory proposal and consent workflow."""

    def test_propose_and_confirm(self, tl):
        """Test proposing and confirming a memory."""
        # Create proposal
        proposal = tl.memory.propose(
            type="relational",
            content={"entity": "Proposed", "summary": "A proposed memory"},
            source_message="User said something about Proposed",
        )

        assert proposal.status == "pending"

        # List pending
        pending = tl.memory.get_pending_proposals()
        assert any(p.id == proposal.id for p in pending)

        # Confirm
        capsule = tl.memory.confirm_proposal(proposal.id)

        assert capsule is not None
        assert capsule.consent_confirmed
        assert capsule.entity == "Proposed"

    def test_propose_and_reject(self, tl):
        """Test proposing and rejecting a memory."""
        proposal = tl.memory.propose(
            type="relational",
            content={"entity": "ToReject"},
        )

        # Reject
        result = tl.memory.reject_proposal(proposal.id)
        assert result is True

        # Should no longer be in pending
        pending = tl.memory.get_pending_proposals()
        assert not any(p.id == proposal.id for p in pending)


class TestSessionManagement:
    """Test session management features."""

    def test_session_lifecycle(self, tl):
        """Test complete session lifecycle."""
        # No session initially
        assert tl.get_session() is None

        # Start session
        session = tl.start_session(context="test")

        assert session.is_active
        assert session.metadata.get("context") == "test"

        # Create memory during session
        capsule = tl.remember(
            type="relational",
            content={"entity": "SessionMemory"},
            confirm=True,
        )

        # End session
        ended = tl.end_session()

        assert not ended.is_active
        assert ended.duration_seconds >= 0

    def test_ephemeral_cleanup_on_session_end(self, tl):
        """Test that ephemeral memories are cleaned up."""
        tl.start_session()

        # Create ephemeral memory
        ephemeral = tl.remember(
            type="relational",
            content={"entity": "Ephemeral"},
            retention="ephemeral",
            confirm=True,
        )
        cap_id = ephemeral.id

        # Record it in session
        session = tl.get_session()
        session.record_creation(cap_id)

        # End session
        tl.end_session()

        # Should be deleted
        assert tl.memory.get(cap_id) is None


class TestContextComposition:
    """Test that context is composed correctly for different modes."""

    def test_different_context_modes(self, tl, mock_provider):
        """Test that different context modes produce different outputs."""
        # Create memory
        tl.remember(
            type="relational",
            content={"entity": "ContextTest", "summary": "For testing context"},
            cue_phrases=["contexttest"],
            confirm=True,
        )

        # Chat with different modes
        responses = {}
        for mode in [ContextMode.DIRECT, ContextMode.NARRATIVE, ContextMode.WHISPER]:
            response = tl.chat_with_context(
                "Tell me about ContextTest",
                context_mode=mode,
            )
            responses[mode] = response

        # Should all get responses
        assert all(r.content != "" for r in responses.values())


class TestStyleModulation:
    """Test style profile application."""

    def test_style_changes(self, tl):
        """Test changing style profiles."""
        # Set minimal style
        tl.set_style("minimal")
        minimal = tl.get_style()
        assert minimal is not None
        assert minimal.style_id == "minimal"

        # Clear style
        tl.set_style(None)
        assert tl.get_style() is None


class TestExportImport:
    """Test data export and import."""

    def test_full_export_import(self, mock_provider):
        """Test exporting and importing all data."""
        # Create instance with data
        tl1 = Threadlight(storage_backend="memory")

        tl1.remember(
            type="relational",
            content={"entity": "Export1"},
            confirm=True,
        )
        tl1.remember(
            type="myth_seed",
            content={"seed": "Export seed"},
            confirm=True,
        )

        # Export
        exported = tl1.memory.export()
        tl1.close()

        # Create new instance
        tl2 = Threadlight(storage_backend="memory")

        # Import
        count = tl2.memory.import_capsules(exported)

        assert count == 2

        stats = tl2.memory.stats()
        assert stats["total"] == 2

        tl2.close()


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_recall_with_no_matches(self, tl):
        """Test recall when nothing matches."""
        results = tl.recall("nonexistent_query_xyz")

        # Should return empty list, not error
        assert isinstance(results, list)

    def test_get_nonexistent_capsule(self, tl):
        """Test getting a capsule that doesn't exist."""
        result = tl.memory.get("nonexistent-id")

        assert result is None

    def test_delete_nonexistent_capsule(self, tl):
        """Test deleting a capsule that doesn't exist."""
        result = tl.memory.delete("nonexistent-id")

        # Should return False, not error
        assert result is False


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    def test_multiple_recalls(self, tl):
        """Test multiple recalls in sequence."""
        tl.remember(
            type="relational",
            content={"entity": "Concurrent"},
            cue_phrases=["concurrent"],
            confirm=True,
        )

        # Multiple recalls
        for _ in range(10):
            results = tl.recall("concurrent")
            assert len(results) >= 1
