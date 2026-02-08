"""Tests for integrated memory recall (woven soft + hard memory)."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from threadlight.context.soft_memory import (
    SoftMemory,
    SoftMemoryConfig,
    WovenMemory,
    EntityMatch,
)
from threadlight.storage.base import Message, MessageSearchResult
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed


class TestEntityMatch:
    """Tests for EntityMatch dataclass."""

    def test_entity_match_hash_case_insensitive(self):
        """Entity matches should hash case-insensitively."""
        e1 = EntityMatch(name="Sarah", source_text="test")
        e2 = EntityMatch(name="sarah", source_text="other")

        assert hash(e1) == hash(e2)
        assert e1 == e2

    def test_entity_match_set_deduplication(self):
        """Same entity name (different case) should dedupe in set."""
        entities = {
            EntityMatch(name="Sarah", source_text="test1"),
            EntityMatch(name="sarah", source_text="test2"),
            EntityMatch(name="SARAH", source_text="test3"),
        }

        assert len(entities) == 1

    def test_entity_match_inequality(self):
        """Different entities should not be equal."""
        e1 = EntityMatch(name="Sarah", source_text="test")
        e2 = EntityMatch(name="John", source_text="test")

        assert e1 != e2


class TestWovenMemory:
    """Tests for WovenMemory dataclass."""

    def test_has_woven_context_both_present(self):
        """has_woven_context returns True when both soft and hard memory exist."""
        capsule = create_relational(entity="Sarah", summary="A friend")
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="test", timestamp=datetime.utcnow(),
            ),
            conversation_name="Test Conv",
        )

        woven = WovenMemory(
            soft_memory_results=[result],
            related_capsules=[capsule],
        )

        assert woven.has_woven_context() is True

    def test_has_woven_context_only_soft(self):
        """has_woven_context returns False with only soft memory."""
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="test", timestamp=datetime.utcnow(),
            ),
            conversation_name="Test Conv",
        )

        woven = WovenMemory(soft_memory_results=[result])

        assert woven.has_woven_context() is False

    def test_has_woven_context_only_hard(self):
        """has_woven_context returns False with only hard memory."""
        capsule = create_relational(entity="Sarah", summary="A friend")

        woven = WovenMemory(related_capsules=[capsule])

        assert woven.has_woven_context() is False

    def test_has_woven_context_empty(self):
        """has_woven_context returns False when empty."""
        woven = WovenMemory()

        assert woven.has_woven_context() is False

    def test_format_for_prompt_empty(self):
        """format_for_prompt returns empty string when empty."""
        woven = WovenMemory()

        assert woven.format_for_prompt() == ""

    def test_format_for_prompt_with_soft_memory(self):
        """format_for_prompt includes soft memory content."""
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="Remember when we talked about Sarah?",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Chat about friends",
        )

        woven = WovenMemory(soft_memory_results=[result])
        formatted = woven.format_for_prompt()

        assert "Sarah" in formatted
        assert "Chat about friends" in formatted

    def test_format_for_prompt_with_woven_context(self):
        """format_for_prompt weaves soft and hard memory together."""
        capsule = create_relational(
            entity="Sarah",
            summary="A thoughtful friend from college",
            quality="warm",
        )
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="Do you remember Sarah from the party?",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Party memories",
        )

        woven = WovenMemory(
            soft_memory_results=[result],
            related_capsules=[capsule],
            entity_capsule_map={"Sarah": [capsule]},
        )
        formatted = woven.format_for_prompt()

        # Should include both conversation and relational context
        assert "Party memories" in formatted
        assert "Sarah" in formatted
        assert "thoughtful friend" in formatted
        assert "warm" in formatted

    def test_format_for_prompt_respects_limits(self):
        """format_for_prompt respects max_soft_memory limit."""
        results = [
            MessageSearchResult(
                message=Message(
                    id=str(i), conversation_id="c1", role="user",
                    content=f"Message {i}", timestamp=datetime.utcnow(),
                ),
                conversation_name=f"Conv {i}",
            )
            for i in range(10)
        ]

        woven = WovenMemory(soft_memory_results=results)
        formatted = woven.format_for_prompt(max_soft_memory=2)

        assert "Message 0" in formatted
        assert "Message 1" in formatted
        assert "Message 9" not in formatted

    def test_get_summary(self):
        """get_summary returns correct counts."""
        capsule = create_relational(entity="Sarah", summary="A friend")
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="test", timestamp=datetime.utcnow(),
            ),
            conversation_name="Test",
        )

        woven = WovenMemory(
            soft_memory_results=[result],
            related_capsules=[capsule],
            entity_capsule_map={"Sarah": [capsule]},
            unmatched_entities=["Unknown"],
        )

        summary = woven.get_summary()

        assert summary["soft_memory_count"] == 1
        assert summary["capsule_count"] == 1
        assert "Sarah" in summary["entities_matched"]
        assert "Unknown" in summary["entities_unmatched"]
        assert summary["has_woven_context"] is True


class TestEntityExtraction:
    """Tests for entity extraction from text."""

    @pytest.fixture
    def soft_memory(self):
        """Create a SoftMemory instance with mock storage."""
        mock_storage = MagicMock()
        return SoftMemory(mock_storage)

    def test_extract_capitalized_names(self, soft_memory):
        """Extract capitalized names from mid-sentence."""
        text = "I was talking to Sarah about the project."
        entities = soft_memory._extract_entities_from_text(text)

        names = {e.name for e in entities}
        assert "Sarah" in names

    def test_extract_possessive_names(self, soft_memory):
        """Extract names from possessive patterns."""
        text = "Sarah's project is going well."
        entities = soft_memory._extract_entities_from_text(text)

        names = {e.name for e in entities}
        assert "Sarah" in names

    def test_extract_about_pattern(self, soft_memory):
        """Extract names from 'about X' patterns."""
        text = "Let me tell you about Sarah and her work."
        entities = soft_memory._extract_entities_from_text(text)

        names = {e.name for e in entities}
        assert "Sarah" in names

    def test_skip_common_words(self, soft_memory):
        """Skip common words that might be capitalized."""
        text = "On Monday I met with The Manager."
        entities = soft_memory._extract_entities_from_text(text)

        names = {e.name.lower() for e in entities}
        assert "monday" not in names
        assert "the" not in names

    def test_multi_word_entities(self, soft_memory):
        """Extract multi-word capitalized names."""
        text = "I discussed it with John Smith yesterday."
        entities = soft_memory._extract_entities_from_text(text)

        names = {e.name for e in entities}
        # Should capture "John Smith" or at least "John"
        assert any("John" in name for name in names)

    def test_short_text_returns_empty(self, soft_memory):
        """Very short text returns no entities."""
        entities = soft_memory._extract_entities_from_text("Hi!")
        assert len(entities) == 0


class TestCapsuleMatching:
    """Tests for capsule-entity matching."""

    @pytest.fixture
    def soft_memory(self):
        """Create a SoftMemory instance with mock storage."""
        mock_storage = MagicMock()
        return SoftMemory(mock_storage)

    def test_match_relational_entity(self, soft_memory):
        """Match relational capsule by entity field."""
        capsule = create_relational(entity="Sarah", summary="A friend")

        assert soft_memory._capsule_matches_entity(capsule, "Sarah") is True
        assert soft_memory._capsule_matches_entity(capsule, "sarah") is True
        assert soft_memory._capsule_matches_entity(capsule, "John") is False

    def test_match_by_cue_phrase(self, soft_memory):
        """Match capsule by cue phrase."""
        capsule = create_relational(
            entity="Sarah",
            summary="A friend",
            cue_phrases=["sarah", "college friend"],
        )

        assert soft_memory._capsule_matches_entity(capsule, "Sarah") is True
        assert soft_memory._capsule_matches_entity(capsule, "college") is True

    def test_match_by_content(self, soft_memory):
        """Match capsule by content dictionary."""
        capsule = create_myth_seed(
            seed="Every story matters",
            origin="Sarah",
            function="Remember origins",
        )

        assert soft_memory._capsule_matches_entity(capsule, "Sarah") is True


class TestRecallWithContext:
    """Tests for the integrated recall_with_context method."""

    @pytest.fixture
    def soft_memory(self):
        """Create a SoftMemory instance with mock storage."""
        mock_storage = MagicMock()
        mock_storage.search_messages.return_value = []
        return SoftMemory(mock_storage)

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock memory orchestrator."""
        orchestrator = MagicMock()
        orchestrator.recall.return_value = []
        return orchestrator

    def test_recall_with_context_no_results(self, soft_memory, mock_orchestrator):
        """recall_with_context returns empty WovenMemory when no matches."""
        woven = soft_memory.recall_with_context(
            message="Hello world",
            orchestrator=mock_orchestrator,
        )

        assert len(woven.soft_memory_results) == 0
        assert len(woven.related_capsules) == 0

    def test_recall_with_context_finds_capsules(self, soft_memory, mock_orchestrator):
        """recall_with_context finds related capsules for entities."""
        # Set up soft memory to return a result mentioning Sarah
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="I was talking to Sarah about the project.",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Work chat",
        )
        soft_memory.storage.search_messages.return_value = [result]

        # Set up orchestrator to return a capsule for Sarah
        sarah_capsule = create_relational(
            entity="Sarah",
            summary="A colleague who works on data science",
            quality="friendly",
        )
        mock_orchestrator.recall.return_value = [sarah_capsule]

        woven = soft_memory.recall_with_context(
            message="Sarah's project",
            orchestrator=mock_orchestrator,
        )

        assert len(woven.soft_memory_results) == 1
        assert len(woven.related_capsules) == 1
        assert "Sarah" in woven.entity_capsule_map

    def test_recall_with_context_deduplicates_capsules(self, soft_memory, mock_orchestrator):
        """recall_with_context deduplicates capsules across entities."""
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="Sarah said something about Sarah's project.",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Chat",
        )
        soft_memory.storage.search_messages.return_value = [result]

        # Same capsule returned for multiple queries
        sarah_capsule = create_relational(entity="Sarah", summary="A friend")
        mock_orchestrator.recall.return_value = [sarah_capsule]

        woven = soft_memory.recall_with_context(
            message="Sarah",
            orchestrator=mock_orchestrator,
        )

        # Should not have duplicate capsules
        assert len(woven.related_capsules) == 1

    def test_recall_with_context_tracks_unmatched(self, soft_memory, mock_orchestrator):
        """recall_with_context tracks entities without matching capsules."""
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="John mentioned the deadline.",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Chat",
        )
        soft_memory.storage.search_messages.return_value = [result]

        # Orchestrator returns empty for John
        mock_orchestrator.recall.return_value = []

        woven = soft_memory.recall_with_context(
            message="John",
            orchestrator=mock_orchestrator,
        )

        # John should be in unmatched entities
        assert "John" in woven.unmatched_entities


class TestChatManagerIntegration:
    """Tests for ChatManager's use of integrated recall."""

    @pytest.fixture
    def mock_threadlight(self):
        """Create a mock Threadlight instance."""
        tl = MagicMock()
        tl.soft_memory = MagicMock()
        tl.memory = MagicMock()
        tl.config.memory.conversation.soft_memory_limit = 5
        return tl

    def test_build_soft_memory_context_uses_woven(self, mock_threadlight):
        """build_soft_memory_context uses woven context by default."""
        from threadlight.managers.chat import ChatManager

        # Set up mock woven memory
        capsule = create_relational(
            entity="Sarah",
            summary="A thoughtful friend",
            quality="warm",
        )
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="Sarah's project is going well",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Project chat",
        )
        woven = WovenMemory(
            soft_memory_results=[result],
            related_capsules=[capsule],
            entity_capsule_map={"Sarah": [capsule]},
        )
        mock_threadlight.soft_memory.recall_with_context.return_value = woven

        manager = ChatManager(mock_threadlight)
        context = manager.build_soft_memory_context("How is Sarah doing?")

        # Should include both conversation and capsule info
        assert "Sarah" in context
        assert "thoughtful friend" in context

    def test_build_soft_memory_context_fallback(self, mock_threadlight):
        """build_soft_memory_context falls back to simple when woven fails."""
        from threadlight.managers.chat import ChatManager

        # Make woven context fail
        mock_threadlight.soft_memory.recall_with_context.side_effect = Exception("Test error")

        # Set up simple recall
        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="test message",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Test",
        )
        mock_threadlight.soft_memory.recall_relevant.return_value = [result]
        mock_threadlight.soft_memory.format_for_prompt.return_value = "formatted"

        manager = ChatManager(mock_threadlight)
        context = manager.build_soft_memory_context("test")

        # Should fall back to simple format
        assert context == "formatted"

    def test_build_soft_memory_context_disabled_integration(self, mock_threadlight):
        """build_soft_memory_context can disable integrated recall."""
        from threadlight.managers.chat import ChatManager

        result = MessageSearchResult(
            message=Message(
                id="1", conversation_id="c1", role="user",
                content="test",
                timestamp=datetime.utcnow(),
            ),
            conversation_name="Test",
        )
        mock_threadlight.soft_memory.recall_relevant.return_value = [result]
        mock_threadlight.soft_memory.format_for_prompt.return_value = "simple format"

        manager = ChatManager(mock_threadlight)
        context = manager.build_soft_memory_context("test", use_integrated_recall=False)

        # Should not call recall_with_context
        mock_threadlight.soft_memory.recall_with_context.assert_not_called()
        assert context == "simple format"
