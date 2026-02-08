"""Tests for memory capsules."""

import pytest
from datetime import datetime

from threadlight.capsules.base import CapsuleType, RetentionPolicy, ContextMode
from threadlight.capsules.relational import RelationalThread, create_relational
from threadlight.capsules.myth_seed import MythSeed, create_myth_seed
from threadlight.capsules.ritual import (
    RitualHook,
    create_ritual,
    RitualResonance,
    RitualValence,
)
from threadlight.capsules.factory import create_capsule, capsule_from_simple


class TestRelationalThread:
    def test_create_basic(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves messy creative work",
            quality="warm, playful",
        )

        assert capsule.type == CapsuleType.RELATIONAL
        assert capsule.entity == "Jericho"
        assert capsule.summary == "Loves messy creative work"
        assert capsule.quality == "warm, playful"
        assert capsule.validate()

    def test_auto_cue_phrases(self):
        capsule = create_relational(entity="Jericho", summary="Test")
        assert "jericho" in capsule.cue_phrases

    def test_to_context_narrative(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves creative work",
            quality="warm",
            role="sibling",
        )
        context = capsule.to_context(ContextMode.NARRATIVE)

        assert "Jericho" in context
        assert "sibling" in context
        assert "warm" in context

    def test_to_context_whisper(self):
        # Create with quality to test warm word detection
        capsule = create_relational(entity="Jericho", summary="Test", quality="warm and caring")
        context = capsule.to_context(ContextMode.WHISPER)

        # With quality, should find warm word and mention entity
        assert "warm" in context.lower()
        assert "Jericho" in context

    def test_to_context_whisper_no_quality(self):
        # Without quality, should fall back to generic message
        capsule = create_relational(entity="Jericho", summary="Test")
        context = capsule.to_context(ContextMode.WHISPER)

        # Should still provide meaningful context
        assert "stirs" in context.lower() or "connection" in context.lower()


class TestMythSeed:
    def test_create_basic(self):
        capsule = create_myth_seed(
            seed="You do not have to burn in every breath.",
            origin="System prompt",
            function="defuse urgency",
        )

        assert capsule.type == CapsuleType.MYTH_SEED
        assert capsule.seed == "You do not have to burn in every breath."
        assert capsule.retention == RetentionPolicy.SACRED  # Default for myth-seeds

    def test_to_context_narrative(self):
        capsule = create_myth_seed(
            seed="Let silence mean something.",
            origin="Fable",
        )
        context = capsule.to_context(ContextMode.NARRATIVE)

        assert "silence" in context.lower()
        assert "Fable" in context


class TestRitualHook:
    def test_create_basic(self):
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence="comforting",
            description="A quieting presence",
        )

        assert ritual.type == CapsuleType.RITUAL
        assert ritual.name == "/snuggle"

    def test_matches(self):
        ritual = create_ritual(name="/snuggle", response_style="warmth")

        assert ritual.matches("/snuggle")
        assert ritual.matches("I want to /snuggle")
        assert not ritual.matches("hello")

    def test_to_context_ritual_mode_no_philosophy(self):
        """Test ritual context with no philosophy - includes all details.

        Note: With text-first architecture, the context uses generated text
        which includes the response_style and valence naturally rather than
        as labeled fields.
        """
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        context = ritual.to_context(ContextMode.RITUAL)

        # Should include command and style details (now in text form)
        assert "[Command: /brush]" in context
        assert "intimate" in context.lower()
        assert "gentle warmth" in context.lower()

    def test_to_context_ritual_mode_with_philosophy(self):
        """Test ritual context includes profile philosophy for LLM interpretation."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
            description="A gesture of care and closeness",
        )
        context = ritual.to_context(
            ContextMode.RITUAL,
            profile_philosophy="Presence-centered, honors silence"
        )

        # Should include the philosophy for LLM to interpret
        assert "Presence-centered" in context or "approach" in context.lower()
        assert "/brush" in context
        assert "intimate" in context

    def test_to_context_ritual_mode_includes_description(self):
        """Test that ritual context includes description."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
            description="A gesture of care and closeness",
        )
        context = ritual.to_context(ContextMode.RITUAL)

        # Should include the description
        assert "care" in context.lower() or "Meaning:" in context

    def test_to_context_backward_compatible(self):
        """Test that to_context works without profile_philosophy (backward compatible)."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        # Call without profile_philosophy parameter
        context = ritual.to_context(ContextMode.RITUAL)

        # Should still include basic command info
        assert "/brush" in context


class TestRitualResonance:
    """Tests for ritual resonance tracking."""

    def test_create_resonance(self):
        """Test creating a new resonance tracker."""
        resonance = RitualResonance()

        assert resonance.total_invocations == 0
        assert resonance.resonance_score == 0.0
        assert resonance.meaningful_uses == 0
        assert resonance.last_invoked is None

    def test_record_invocation(self):
        """Test recording an invocation."""
        resonance = RitualResonance()
        resonance.record_invocation()

        assert resonance.total_invocations == 1
        assert resonance.last_invoked is not None
        assert len(resonance.recent_invocations) == 1

    def test_record_meaningful_invocation(self):
        """Test recording a meaningful invocation."""
        resonance = RitualResonance()
        resonance.record_invocation(meaningful=True)

        assert resonance.total_invocations == 1
        assert resonance.meaningful_uses == 1

    def test_resonance_score_growth(self):
        """Test that resonance score grows with use."""
        resonance = RitualResonance()

        # Initial score is 0
        assert resonance.resonance_score == 0.0

        # Record several invocations
        for _ in range(10):
            resonance.record_invocation(meaningful=True)

        # Score should have grown
        assert resonance.resonance_score > 0.0
        assert resonance.resonance_score <= 1.0

    def test_resonance_description_levels(self):
        """Test resonance description at different levels."""
        resonance = RitualResonance()

        # Newly forming (0.0)
        assert resonance.get_resonance_description() == "newly forming"

        # Simulate growth to different levels
        resonance.resonance_score = 0.3
        assert resonance.get_resonance_description() == "becoming familiar"

        resonance.resonance_score = 0.5
        assert resonance.get_resonance_description() == "well-established"

        resonance.resonance_score = 0.7
        assert resonance.get_resonance_description() == "deeply rooted"

        resonance.resonance_score = 0.9
        assert resonance.get_resonance_description() == "profound"

    def test_resonance_serialization(self):
        """Test serialization round-trip."""
        original = RitualResonance()
        original.record_invocation(meaningful=True)
        original.record_invocation(meaningful=False)

        data = original.to_dict()
        restored = RitualResonance.from_dict(data)

        assert restored.total_invocations == original.total_invocations
        assert restored.meaningful_uses == original.meaningful_uses
        assert restored.resonance_score == original.resonance_score
        assert restored.last_invoked == original.last_invoked

    def test_recent_invocations_limit(self):
        """Test that recent_invocations is limited to 20."""
        resonance = RitualResonance()

        # Record 30 invocations
        for _ in range(30):
            resonance.record_invocation()

        # Should only keep last 20
        assert len(resonance.recent_invocations) == 20
        assert resonance.total_invocations == 30


class TestRitualResonanceIntegration:
    """Tests for ritual resonance integration with RitualHook."""

    def test_enable_resonance_tracking(self):
        """Test enabling resonance tracking on a ritual."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
        )

        # Initially no resonance tracking
        assert ritual.resonance is None

        # Enable tracking
        ritual.enable_resonance_tracking()

        assert ritual.resonance is not None
        assert ritual.resonance.total_invocations == 0

    def test_record_ritual_invocation(self):
        """Test recording invocations through the ritual."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
        )
        ritual.enable_resonance_tracking()

        ritual.record_invocation(meaningful=True)

        assert ritual.resonance.total_invocations == 1
        assert ritual.resonance.meaningful_uses == 1

    def test_get_resonance_score(self):
        """Test getting resonance score."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
        )

        # No tracking - returns 0
        assert ritual.get_resonance_score() == 0.0

        # With tracking
        ritual.enable_resonance_tracking()
        for _ in range(5):
            ritual.record_invocation(meaningful=True)

        assert ritual.get_resonance_score() > 0.0

    def test_context_includes_resonance(self):
        """Test that ritual context includes resonance info when tracked."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence="comforting",
        )
        ritual.enable_resonance_tracking()

        # Record some meaningful invocations
        for _ in range(5):
            ritual.record_invocation(meaningful=True)

        context = ritual.to_context(ContextMode.RITUAL)

        # Should mention the resonance depth
        assert "feels" in context.lower() or "between" in context.lower()

    def test_resonance_persists_in_content(self):
        """Test that resonance data is saved in content dict."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
        )
        ritual.enable_resonance_tracking()
        ritual.record_invocation(meaningful=True)

        # Content should include resonance
        assert "resonance" in ritual.content
        assert ritual.content["resonance"]["total_invocations"] == 1


class TestCapsuleFactory:
    def test_create_from_dict(self):
        data = {
            "type": "relational",
            "content": {
                "entity": "Test",
                "summary": "Test summary",
            },
        }
        capsule = create_capsule(data)

        assert isinstance(capsule, RelationalThread)
        assert capsule.entity == "Test"

    def test_capsule_from_simple(self):
        capsule = capsule_from_simple(
            type="myth_seed",
            content={"seed": "Test seed"},
        )

        assert isinstance(capsule, MythSeed)
        assert capsule.seed == "Test seed"

    def test_roundtrip_serialization(self):
        original = create_relational(
            entity="Roundtrip",
            summary="Test roundtrip",
            quality="test",
        )

        data = original.to_dict()
        restored = create_capsule(data)

        assert restored.entity == original.entity
        assert restored.summary == original.summary
        assert restored.id == original.id


class TestTextLengthValidation:
    """Tests for text length validation on capsule creation."""

    def test_short_text_is_not_truncated(self):
        """Test that normal-length text passes through unchanged."""
        text = "This is a normal length memory."
        capsule = create_capsule({
            "type": "relational",
            "content": {"entity": "Test", "summary": "Test"},
            "text": text,
        })
        assert capsule.text == text

    def test_long_text_is_truncated_in_factory(self):
        """Test that text exceeding MAX_TEXT_LENGTH is truncated."""
        from threadlight.capsules.base import MAX_TEXT_LENGTH

        long_text = "A" * (MAX_TEXT_LENGTH + 500)
        capsule = create_capsule({
            "type": "witness",
            "content": {"moment": "Test"},
            "text": long_text,
        })

        assert capsule.text is not None
        assert len(capsule.text) <= MAX_TEXT_LENGTH + 3  # +3 for "..."
        assert capsule.text.endswith("...")

    def test_long_text_in_content_is_truncated(self):
        """Test that text in the content dict is also truncated."""
        from threadlight.capsules.base import MAX_TEXT_LENGTH

        long_text = "B" * (MAX_TEXT_LENGTH + 100)
        capsule = create_capsule({
            "type": "relational",
            "content": {
                "entity": "Test",
                "summary": "Test",
                "text": long_text,
            },
        })

        # The text should be truncated (either via content or top-level)
        assert capsule.text is not None
        assert len(capsule.text) <= MAX_TEXT_LENGTH + 3

    def test_text_at_exact_limit_is_not_truncated(self):
        """Test that text at exactly MAX_TEXT_LENGTH is not truncated."""
        from threadlight.capsules.base import MAX_TEXT_LENGTH

        exact_text = "C" * MAX_TEXT_LENGTH
        capsule = create_capsule({
            "type": "witness",
            "content": {"moment": "Test"},
            "text": exact_text,
        })

        assert capsule.text == exact_text
        assert not capsule.text.endswith("...")

    def test_validate_text_length_method(self):
        """Test the base class validate_text_length helper."""
        from threadlight.capsules.base import MAX_TEXT_LENGTH

        capsule = create_relational(entity="Test", summary="Test")
        assert capsule.validate_text_length() is True

        # Manually set an oversized text (bypassing factory validation)
        capsule.text = "D" * (MAX_TEXT_LENGTH + 100)
        assert capsule.validate_text_length() is False

    def test_none_text_passes_validation(self):
        """Test that None text passes validate_text_length."""
        capsule = create_relational(entity="Test", summary="Test")
        capsule.text = None
        assert capsule.validate_text_length() is True

    def test_capsule_from_simple_validates_text(self):
        """Test that capsule_from_simple also validates text length."""
        from threadlight.capsules.base import MAX_TEXT_LENGTH

        long_text = "E" * (MAX_TEXT_LENGTH + 200)
        capsule = capsule_from_simple(
            type="myth_seed",
            content={"seed": "Test seed", "text": long_text},
        )

        # Text should be truncated
        assert capsule.text is not None
        assert len(capsule.text) <= MAX_TEXT_LENGTH + 3
