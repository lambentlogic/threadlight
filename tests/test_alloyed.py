"""Tests for AlloyedProfileEngine - model selection strategies."""

import pytest
from unittest.mock import MagicMock, patch
import random

from threadlight.profiles import (
    Profile,
    ModelStrategy,
    AlloyedConfig,
    RoutingRule,
    AlloyedProfileEngine,
)
from threadlight.storage.memory import InMemoryStorage


@pytest.fixture
def storage():
    """Create an in-memory storage backend for testing."""
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def base_profile():
    """Create a base profile for testing."""
    return Profile(
        id="test-profile",
        name="Test Profile",
        primary_model="model-a",
    )


class TestSingleStrategy:
    """Tests for SINGLE model selection strategy."""

    def test_always_returns_primary_model(self, storage, base_profile):
        """SINGLE strategy should always return the primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.SINGLE,
            model_pool=["model-a", "model-b"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Multiple calls should all return primary_model
        for _ in range(10):
            assert engine.select_model("test message") == "model-a"

    def test_ignores_model_pool(self, storage, base_profile):
        """SINGLE strategy should ignore the model pool."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.SINGLE,
            model_pool=["model-b", "model-c"],  # Different from primary
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"  # Still returns primary


class TestAlternatingStrategy:
    """Tests for ALTERNATING model selection strategy."""

    def test_alternates_between_two_models(self, storage, base_profile):
        """ALTERNATING should cycle through two models."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        results = [engine.select_model("test") for _ in range(6)]
        assert results == ["model-a", "model-b", "model-a", "model-b", "model-a", "model-b"]

    def test_cycles_through_multiple_models(self, storage, base_profile):
        """ALTERNATING should cycle through all models in pool."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b", "model-c"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        results = [engine.select_model("test") for _ in range(9)]
        expected = ["model-a", "model-b", "model-c"] * 3
        assert results == expected

    def test_empty_pool_returns_primary(self, storage, base_profile):
        """ALTERNATING with empty pool should return primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=[],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"


class TestRoundRobinStrategy:
    """Tests for ROUND_ROBIN model selection strategy."""

    def test_cycles_through_models(self, storage, base_profile):
        """ROUND_ROBIN should cycle through models in order."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUND_ROBIN,
            model_pool=["model-a", "model-b", "model-c"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        results = [engine.select_model("test") for _ in range(6)]
        expected = ["model-a", "model-b", "model-c", "model-a", "model-b", "model-c"]
        assert results == expected


class TestRatioStrategy:
    """Tests for RATIO model selection strategy."""

    def test_follows_ratio_pattern(self, storage, base_profile):
        """RATIO strategy should follow the specified ratio pattern."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.RATIO,
            ratios={"model-a": 2, "model-b": 1},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # 2:1 ratio means: A, A, B, A, A, B, ...
        results = [engine.select_model("test") for _ in range(6)]
        assert results == ["model-a", "model-a", "model-b", "model-a", "model-a", "model-b"]

    def test_complex_ratio(self, storage, base_profile):
        """RATIO strategy should handle complex ratios."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.RATIO,
            ratios={"model-a": 3, "model-b": 2, "model-c": 1},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Pattern: A, A, A, B, B, C, ...
        results = [engine.select_model("test") for _ in range(12)]
        expected = ["model-a", "model-a", "model-a", "model-b", "model-b", "model-c"] * 2
        assert results == expected

    def test_no_ratios_returns_primary(self, storage, base_profile):
        """RATIO with no ratios defined should return primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.RATIO,
            ratios=None,
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"


class TestWeightedStrategy:
    """Tests for WEIGHTED model selection strategy."""

    def test_respects_weights_distribution(self, storage, base_profile):
        """WEIGHTED strategy should respect probability distribution."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            weights={"model-a": 0.9, "model-b": 0.1},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Run many selections and check distribution
        random.seed(42)  # For reproducibility
        results = [engine.select_model("test") for _ in range(1000)]

        count_a = results.count("model-a")
        count_b = results.count("model-b")

        # With 90/10 weights, model-a should be ~900, model-b ~100
        # Allow some variance (within 10%)
        assert 800 < count_a < 950
        assert 50 < count_b < 200

    def test_equal_weights(self, storage, base_profile):
        """WEIGHTED with equal weights should distribute evenly."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            weights={"model-a": 1.0, "model-b": 1.0},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        random.seed(42)
        results = [engine.select_model("test") for _ in range(1000)]

        count_a = results.count("model-a")
        count_b = results.count("model-b")

        # Should be roughly 50/50 (within 10%)
        assert 400 < count_a < 600
        assert 400 < count_b < 600

    def test_no_weights_returns_primary(self, storage, base_profile):
        """WEIGHTED with no weights should return primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            weights=None,
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"


class TestDynamicStrategy:
    """Tests for DYNAMIC model selection strategy."""

    def test_short_messages_prefer_first_models(self, storage, base_profile):
        """Short, simple messages should prefer earlier (simpler) models."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.DYNAMIC,
            model_pool=["simple-model", "medium-model", "complex-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Short simple message
        result = engine.select_model("Hi")
        assert result == "simple-model"

    def test_long_messages_prefer_later_models(self, storage, base_profile):
        """Long messages should prefer later (more capable) models."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.DYNAMIC,
            model_pool=["simple-model", "medium-model", "complex-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Long message (>500 chars)
        long_message = "Please help me with this complex problem. " * 20
        result = engine.select_model(long_message)
        assert result in ["medium-model", "complex-model"]

    def test_code_keywords_increase_complexity(self, storage, base_profile):
        """Messages with code keywords should prefer more capable models."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.DYNAMIC,
            model_pool=["simple-model", "medium-model", "complex-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Code-related message
        result = engine.select_model("def calculate_sum(): return sum(items)")
        assert result in ["medium-model", "complex-model"]

    def test_math_keywords_increase_complexity(self, storage, base_profile):
        """Messages with math keywords should prefer more capable models."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.DYNAMIC,
            model_pool=["simple-model", "medium-model", "complex-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Math-related message with enough complexity to trigger higher model
        # (derivative keyword + longer message + question mark)
        result = engine.select_model(
            "Can you help me calculate the derivative of f(x) = x^2 + 3x - 5? "
            "I need to find the rate of change at x=2."
        )
        assert result in ["medium-model", "complex-model"]

    def test_single_model_pool(self, storage, base_profile):
        """DYNAMIC with single model should return that model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.DYNAMIC,
            model_pool=["only-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("complex question with code def function()") == "only-model"


class TestRoutedStrategy:
    """Tests for ROUTED model selection strategy."""

    def test_keyword_matching(self, storage, base_profile):
        """ROUTED should match keyword rules."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="keyword",
                    pattern="urgent",
                    target_model="fast-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        assert engine.select_model("This is urgent!") == "fast-model"
        assert engine.select_model("URGENT: Help needed") == "fast-model"
        assert engine.select_model("normal message") == "model-a"  # fallback

    def test_regex_matching(self, storage, base_profile):
        """ROUTED should match regex rules."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="regex",
                    pattern=r"\b\d{4}-\d{2}-\d{2}\b",  # Date pattern
                    target_model="date-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        assert engine.select_model("Meeting on 2024-01-15") == "date-model"
        assert engine.select_model("No date here") == "model-a"

    def test_length_matching(self, storage, base_profile):
        """ROUTED should match length rules."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="length",
                    pattern=">100",
                    target_model="long-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        long_msg = "x" * 150
        short_msg = "short"

        assert engine.select_model(long_msg) == "long-model"
        assert engine.select_model(short_msg) == "model-a"

    def test_length_operators(self, storage, base_profile):
        """ROUTED should handle all length comparison operators."""
        # Test >= operator
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(match_type="length", pattern=">=10", target_model="m1", priority=1),
            ],
        )
        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("x" * 10) == "m1"
        assert engine.select_model("x" * 9) == "model-a"

        # Test <= operator
        base_profile.alloyed_config.routing_rules = [
            RoutingRule(match_type="length", pattern="<=5", target_model="m2", priority=1),
        ]
        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("x" * 5) == "m2"
        assert engine.select_model("x" * 6) == "model-a"

        # Test < operator
        base_profile.alloyed_config.routing_rules = [
            RoutingRule(match_type="length", pattern="<10", target_model="m3", priority=1),
        ]
        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("x" * 9) == "m3"
        assert engine.select_model("x" * 10) == "model-a"

    def test_starts_with_matching(self, storage, base_profile):
        """ROUTED should match starts_with rules."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="starts_with",
                    pattern="help",
                    target_model="help-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        assert engine.select_model("Help me please") == "help-model"
        assert engine.select_model("HELP!") == "help-model"
        assert engine.select_model("I need help") == "model-a"

    def test_ends_with_matching(self, storage, base_profile):
        """ROUTED should match ends_with rules."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="ends_with",
                    pattern="please",
                    target_model="polite-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        assert engine.select_model("Help me please") == "polite-model"
        assert engine.select_model("PLEASE") == "polite-model"
        assert engine.select_model("Please help") == "model-a"

    def test_priority_ordering(self, storage, base_profile):
        """ROUTED should evaluate rules by priority (highest first)."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="keyword",
                    pattern="urgent",
                    target_model="urgent-model",
                    priority=5,
                ),
                RoutingRule(
                    match_type="keyword",
                    pattern="help",
                    target_model="help-model",
                    priority=10,  # Higher priority
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        # Message with both keywords should match higher priority
        assert engine.select_model("urgent help needed") == "help-model"

    def test_fallback_to_primary(self, storage, base_profile):
        """ROUTED should fall back to primary_model if no rules match."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="keyword",
                    pattern="special",
                    target_model="special-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("normal message") == "model-a"

    def test_no_rules_returns_primary(self, storage, base_profile):
        """ROUTED with no rules should return primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("any message") == "model-a"

    def test_invalid_regex_skipped(self, storage, base_profile):
        """ROUTED should handle invalid regex patterns gracefully."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="regex",
                    pattern="[invalid",  # Invalid regex
                    target_model="regex-model",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        # Should fall back to primary, not raise exception
        assert engine.select_model("test") == "model-a"


class TestStatePersistence:
    """Tests for state persistence across engine instances."""

    def test_state_persists_across_instances(self, storage, base_profile):
        """State should persist and restore correctly."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )

        # Save profile to storage first
        storage.save_profile(base_profile)

        # First engine instance
        engine1 = AlloyedProfileEngine(base_profile, storage)
        result1 = engine1.select_model("test")  # model-a
        result2 = engine1.select_model("test")  # model-b

        assert result1 == "model-a"
        assert result2 == "model-b"

        # Create new engine instance - should continue from saved state
        engine2 = AlloyedProfileEngine(base_profile, storage)
        result3 = engine2.select_model("test")  # Should be model-a (continuing)

        assert result3 == "model-a"

    def test_turn_count_persists(self, storage, base_profile):
        """Turn count should persist across instances."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.SINGLE,
        )
        storage.save_profile(base_profile)

        engine1 = AlloyedProfileEngine(base_profile, storage)
        for _ in range(5):
            engine1.select_model("test")

        stats1 = engine1.get_model_usage_stats()
        assert stats1["turn_count"] == 5

        # New instance should have same count
        engine2 = AlloyedProfileEngine(base_profile, storage)
        stats2 = engine2.get_model_usage_stats()
        assert stats2["turn_count"] == 5

    def test_model_counts_persist(self, storage, base_profile):
        """Model usage counts should persist across instances."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )
        storage.save_profile(base_profile)

        engine1 = AlloyedProfileEngine(base_profile, storage)
        for _ in range(4):  # 2 each
            engine1.select_model("test")

        # New instance
        engine2 = AlloyedProfileEngine(base_profile, storage)
        stats = engine2.get_model_usage_stats()

        assert stats["model_counts"]["model-a"] == 2
        assert stats["model_counts"]["model-b"] == 2

    def test_reset_state(self, storage, base_profile):
        """reset_state should clear all state."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )
        storage.save_profile(base_profile)

        engine = AlloyedProfileEngine(base_profile, storage)
        for _ in range(5):
            engine.select_model("test")

        # Reset
        engine.reset_state()

        stats = engine.get_model_usage_stats()
        assert stats["turn_count"] == 0
        assert stats["current_index"] == 0
        assert stats["model_counts"] == {}


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_alloyed_config(self, storage):
        """Profile without alloyed_config should get default."""
        profile = Profile(
            id="test",
            name="Test",
            primary_model="default-model",
            alloyed_config=None,
        )

        engine = AlloyedProfileEngine(profile, storage)
        assert engine.select_model("test") == "default-model"

    def test_empty_model_pool(self, storage, base_profile):
        """Empty model pool should fall back to primary_model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=[],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"

    def test_single_model_in_pool(self, storage, base_profile):
        """Single model in pool should always return that model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["only-model"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        for _ in range(5):
            assert engine.select_model("test") == "only-model"

    def test_unknown_match_type(self, storage, base_profile):
        """Unknown match type in routing rule should not match."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="unknown_type",
                    pattern="test",
                    target_model="target",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        # Should fall back to primary
        assert engine.select_model("test") == "model-a"

    def test_invalid_length_pattern(self, storage, base_profile):
        """Invalid length pattern should not match."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            routing_rules=[
                RoutingRule(
                    match_type="length",
                    pattern="not_a_number",
                    target_model="target",
                    priority=10,
                ),
            ],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"

    def test_zero_weights(self, storage, base_profile):
        """Zero total weights should return primary model."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            weights={"model-a": 0, "model-b": 0},
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        assert engine.select_model("test") == "model-a"


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_model_usage_stats(self, storage, base_profile):
        """get_model_usage_stats should return correct statistics."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)
        for _ in range(4):
            engine.select_model("test")

        stats = engine.get_model_usage_stats()

        assert stats["turn_count"] == 4
        assert stats["model_counts"]["model-a"] == 2
        assert stats["model_counts"]["model-b"] == 2
        assert stats["model_percentages"]["model-a"] == 50.0
        assert stats["model_percentages"]["model-b"] == 50.0
        assert stats["strategy"] == "alternating"

    def test_preview_next_models_alternating(self, storage, base_profile):
        """preview_next_models should show upcoming selections for ALTERNATING."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.ALTERNATING,
            model_pool=["model-a", "model-b"],
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        preview = engine.preview_next_models(4)
        assert preview == ["model-a", "model-b", "model-a", "model-b"]

        # State should not be modified
        assert engine.config.current_index == 0

    def test_preview_next_models_ratio(self, storage, base_profile):
        """preview_next_models should show upcoming selections for RATIO."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.RATIO,
            ratios={"model-a": 2, "model-b": 1},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        preview = engine.preview_next_models(6)
        assert preview == ["model-a", "model-a", "model-b", "model-a", "model-a", "model-b"]

    def test_preview_next_models_single(self, storage, base_profile):
        """preview_next_models should show primary_model for SINGLE."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.SINGLE,
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        preview = engine.preview_next_models(3)
        assert preview == ["model-a", "model-a", "model-a"]

    def test_preview_next_models_weighted(self, storage, base_profile):
        """preview_next_models for WEIGHTED should show primary_model (non-deterministic)."""
        base_profile.alloyed_config = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            weights={"model-a": 0.5, "model-b": 0.5},
        )

        engine = AlloyedProfileEngine(base_profile, storage)

        preview = engine.preview_next_models(3)
        # Non-deterministic strategies show primary
        assert preview == ["model-a", "model-a", "model-a"]
