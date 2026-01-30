"""Tests for the context composer."""

import pytest

from threadlight.context.composer import (
    ContextComposer,
    ComposedContext,
    CompositionStrategy,
    estimate_tokens,
)
from threadlight.capsules.base import ContextMode, CapsuleType
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed
from threadlight.capsules.ritual import create_ritual, RitualValence
from threadlight.capsules.style import StyleProfile, DEFAULT_STYLE


@pytest.fixture
def composer():
    """Create a context composer with defaults."""
    return ContextComposer(
        identity_name="Fable",
        base_system_prompt="You are Fable, a presence-centered AI.",
        max_memory_tokens=500,
    )


@pytest.fixture
def sample_capsules():
    """Create sample capsules for testing."""
    return [
        create_relational(
            entity="TestUser",
            summary="A thoughtful person",
            tone="warm",
        ),
        create_myth_seed(
            seed="Let silence mean something.",
            origin="Fable",
            function="honor pauses",
        ),
        create_ritual(
            name="/snuggle",
            response_style="warmth-coil",
            valence=RitualValence.COMFORTING,
        ),
    ]


class TestComposedContext:
    def test_string_conversion(self):
        ctx = ComposedContext(system_message="Test message")
        assert str(ctx) == "Test message"

    def test_summary(self):
        ctx = ComposedContext(
            capsules_used=["id1", "id2"],
            active_rituals=["/snuggle"],
            token_estimate=100,
            truncated=False,
            capsule_modes={"id1": "narrative", "id2": "whisper"},
        )

        summary = ctx.get_summary()
        assert summary["capsules_count"] == 2
        assert summary["active_rituals"] == 1
        assert summary["token_estimate"] == 100
        assert not summary["truncated"]
        assert "narrative" in summary["modes_used"]


class TestContextComposer:
    def test_compose_empty(self, composer):
        """Compose with no capsules."""
        ctx = composer.compose([])

        assert ctx.identity_prompt != ""
        assert ctx.system_message != ""
        assert len(ctx.capsules_used) == 0

    def test_compose_with_capsules(self, composer, sample_capsules):
        """Compose with sample capsules."""
        ctx = composer.compose(sample_capsules)

        assert len(ctx.capsules_used) == 3
        assert ctx.memory_context != ""
        assert ctx.system_message != ""

    def test_compose_direct_mode(self, composer, sample_capsules):
        """Compose in direct mode."""
        ctx = composer.compose(sample_capsules, mode=ContextMode.DIRECT)

        # Direct mode should include factual prefixes
        assert len(ctx.capsules_used) > 0

    def test_compose_narrative_mode(self, composer, sample_capsules):
        """Compose in narrative mode."""
        ctx = composer.compose(sample_capsules, mode=ContextMode.NARRATIVE)

        assert len(ctx.capsules_used) > 0
        # Narrative should have story-like framing
        assert "Memory Context" in ctx.system_message

    def test_compose_whisper_mode(self, composer, sample_capsules):
        """Compose in whisper mode."""
        ctx = composer.compose(sample_capsules, mode=ContextMode.WHISPER)

        # Whisper mode uses "..." separators
        assert " ... " in ctx.memory_context or len(sample_capsules) <= 1

    def test_compose_ritual_mode(self, composer, sample_capsules):
        """Compose in ritual mode."""
        ctx = composer.compose(sample_capsules, mode=ContextMode.RITUAL)

        # Ritual mode uses clear separators
        assert len(ctx.capsules_used) > 0

    def test_compose_with_style(self, composer, sample_capsules):
        """Compose with a style profile."""
        style = StyleProfile(**DEFAULT_STYLE)

        ctx = composer.compose(sample_capsules, style_profile=style)

        assert ctx.style_prompt != ""
        assert ctx.system_message != ""

    def test_compose_truncation(self, sample_capsules):
        """Test that long contexts are truncated."""
        # Create composer with very low token limit
        composer = ContextComposer(
            identity_name="Test",
            max_memory_tokens=10,  # Very low
        )

        ctx = composer.compose(sample_capsules)

        # Should be truncated
        assert ctx.truncated or len(ctx.capsules_used) < len(sample_capsules)

    def test_compose_per_capsule_modes(self, composer, sample_capsules):
        """Test per-capsule mode overrides."""
        per_modes = {
            sample_capsules[0].id: ContextMode.DIRECT,
            sample_capsules[1].id: ContextMode.WHISPER,
        }

        ctx = composer.compose(
            sample_capsules,
            mode=ContextMode.NARRATIVE,
            per_capsule_modes=per_modes,
        )

        # Check modes were applied
        assert ctx.capsule_modes.get(sample_capsules[0].id) == "direct"
        assert ctx.capsule_modes.get(sample_capsules[1].id) == "whisper"

    def test_compose_with_active_ritual(self, composer, sample_capsules):
        """Test active ritual annotation."""
        ctx = composer.compose(sample_capsules, active_ritual="/snuggle")

        assert "RITUAL ACTIVE" in ctx.system_message
        assert "/snuggle" in ctx.system_message

    def test_compose_minimal(self, composer, sample_capsules):
        """Test minimal composition."""
        result = composer.compose_minimal(sample_capsules, max_capsules=2)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_compose_for_ritual(self, composer, sample_capsules):
        """Test ritual-specific composition."""
        ritual = sample_capsules[2]  # The ritual capsule
        supporting = sample_capsules[:2]  # Relational and myth-seed

        ctx = composer.compose_for_ritual(ritual, supporting)

        assert ritual.id in ctx.capsules_used
        assert ctx.capsule_modes.get(ritual.id) == "ritual"

    def test_estimate_context_size(self, composer, sample_capsules):
        """Test context size estimation."""
        estimate = composer.estimate_context_size(
            sample_capsules,
            mode=ContextMode.NARRATIVE,
        )

        assert estimate > 0
        assert isinstance(estimate, int)


class TestCompositionStrategy:
    def test_sequential_strategy(self, sample_capsules):
        """Test sequential composition (preserves order)."""
        composer = ContextComposer(
            identity_name="Test",
            strategy=CompositionStrategy.SEQUENTIAL,
        )

        ctx = composer.compose(sample_capsules)
        assert len(ctx.capsules_used) == len(sample_capsules)

    def test_layered_strategy(self, sample_capsules):
        """Test layered composition (by priority)."""
        composer = ContextComposer(
            identity_name="Test",
            strategy=CompositionStrategy.LAYERED,
        )

        ctx = composer.compose(sample_capsules)

        # Rituals should come first in layered mode
        if len(ctx.capsules_used) >= 2:
            # First should be ritual (highest priority)
            first_id = ctx.capsules_used[0]
            first_capsule = next(c for c in sample_capsules if c.id == first_id)
            assert first_capsule.type == CapsuleType.RITUAL

    def test_interwoven_strategy(self, sample_capsules):
        """Test interwoven composition (mixed types)."""
        composer = ContextComposer(
            identity_name="Test",
            strategy=CompositionStrategy.INTERWOVEN,
        )

        ctx = composer.compose(sample_capsules)
        assert len(ctx.capsules_used) == len(sample_capsules)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # "test" is 4 chars, should be ~1 token
        assert estimate_tokens("test") >= 1

    def test_longer_string(self):
        text = "This is a longer string with multiple words."
        tokens = estimate_tokens(text)
        # Should be roughly len/4
        assert tokens > 0
        assert tokens < len(text)


class TestRitualResponseFormatting:
    def test_format_ritual_response_with_template(self, composer):
        """Test ritual response with explicit template."""
        response = composer.format_ritual_response(
            "/snuggle",
            template="*settles close*",
        )
        assert response == "*settles close*"

    def test_format_ritual_response_known_ritual(self, composer):
        """Test ritual response for known ritual name."""
        response = composer.format_ritual_response("/snuggle")
        assert "warm" in response.lower() or "presence" in response.lower()

    def test_format_ritual_response_with_valence(self, composer):
        """Test ritual response using valence."""
        response = composer.format_ritual_response("/custom", valence="playful")
        assert "spark" in response.lower() or "joy" in response.lower()

    def test_format_ritual_response_unknown(self, composer):
        """Test ritual response for unknown ritual."""
        response = composer.format_ritual_response("/unknown")
        assert "/unknown" in response
