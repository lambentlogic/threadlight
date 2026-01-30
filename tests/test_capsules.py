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
    RITUAL_DEPTH_CEREMONIAL,
    RITUAL_DEPTH_FUNCTIONAL,
    RITUAL_DEPTH_MINIMAL,
)
from threadlight.capsules.factory import create_capsule, capsule_from_simple


class TestRelationalThread:
    def test_create_basic(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves messy creative work",
            tone="warm, playful",
        )

        assert capsule.type == CapsuleType.RELATIONAL
        assert capsule.entity == "Jericho"
        assert capsule.summary == "Loves messy creative work"
        assert capsule.tone == "warm, playful"
        assert capsule.validate()

    def test_auto_cue_phrases(self):
        capsule = create_relational(entity="Jericho", summary="Test")
        assert "jericho" in capsule.cue_phrases

    def test_to_context_narrative(self):
        capsule = create_relational(
            entity="Jericho",
            summary="Loves creative work",
            tone="warm",
            role="sibling",
        )
        context = capsule.to_context(ContextMode.NARRATIVE)

        assert "Jericho" in context
        assert "sibling" in context
        assert "warm" in context

    def test_to_context_whisper(self):
        capsule = create_relational(entity="Jericho", summary="Test")
        context = capsule.to_context(ContextMode.WHISPER)

        assert "warmth" in context.lower()
        assert "Jericho" in context


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

    def test_to_context_ritual_mode_functional(self):
        """Test functional ritual depth (default) - efficient, brief."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        context = ritual.to_context(ContextMode.RITUAL, ritual_depth=RITUAL_DEPTH_FUNCTIONAL)

        # Functional mode uses bracketed, pipe-separated format
        assert "[Ritual: /brush]" in context
        assert "Valence: intimate" in context
        assert "Style: gentle warmth" in context
        # Should NOT have ceremonial language
        assert "honored" not in context.lower()
        assert "presence" not in context.lower()

    def test_to_context_ritual_mode_ceremonial(self):
        """Test ceremonial ritual depth - full presence-based language."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
            description="A gesture of care and closeness",
        )
        context = ritual.to_context(ContextMode.RITUAL, ritual_depth=RITUAL_DEPTH_CEREMONIAL)

        # Ceremonial mode uses presence-based language
        assert "honored" in context.lower()
        assert "presence" in context.lower()
        assert "/brush" in context
        assert "intimate" in context
        # Should include description
        assert "care" in context.lower() or "meaning" in context.lower()

    def test_to_context_ritual_mode_minimal(self):
        """Test minimal ritual depth - just acknowledgment."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        context = ritual.to_context(ContextMode.RITUAL, ritual_depth=RITUAL_DEPTH_MINIMAL)

        # Minimal mode is very brief
        assert "/brush" in context
        assert "active" in context.lower()
        # Should NOT have detailed info
        assert "gentle warmth" not in context
        assert "intimate" not in context

    def test_to_context_backward_compatible(self):
        """Test that to_context works without ritual_depth (backward compatible)."""
        ritual = create_ritual(
            name="/brush",
            response_style="gentle warmth",
            valence="intimate",
        )
        # Call without ritual_depth parameter
        context = ritual.to_context(ContextMode.RITUAL)

        # Should default to functional
        assert "[Ritual: /brush]" in context


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

    def test_ceremonial_context_includes_resonance(self):
        """Test that ceremonial context includes resonance info."""
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence="comforting",
        )
        ritual.enable_resonance_tracking()

        # Record some meaningful invocations
        for _ in range(5):
            ritual.record_invocation(meaningful=True)

        context = ritual.to_context(ContextMode.RITUAL, ritual_depth=RITUAL_DEPTH_CEREMONIAL)

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
            tone="test",
        )

        data = original.to_dict()
        restored = create_capsule(data)

        assert restored.entity == original.entity
        assert restored.summary == original.summary
        assert restored.id == original.id
