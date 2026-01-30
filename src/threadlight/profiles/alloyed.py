"""
AlloyedProfileEngine for Threadlight.

Implements model selection strategies for alloyed (multi-model) profiles.
An "alloyed" profile can use multiple models based on various strategies,
allowing for sophisticated model routing and load balancing.
"""

from __future__ import annotations

import random
import re
from typing import Optional, Any, TYPE_CHECKING

from threadlight.profiles.profile import (
    Profile,
    ModelStrategy,
    AlloyedConfig,
    RoutingRule,
)

if TYPE_CHECKING:
    from threadlight.storage.base import StorageBackend


class AlloyedProfileEngine:
    """
    Engine for selecting which model to use based on the profile's strategy.

    This engine implements all model selection strategies defined in ModelStrategy,
    maintaining state across calls and persisting that state to storage.

    Strategies:
        - SINGLE: Always use primary_model
        - ALTERNATING: Alternate between models in pool (A, B, A, B, ...)
        - ROUND_ROBIN: Cycle through all models in order
        - RATIO: Use models according to specified ratios (e.g., 2:1)
        - WEIGHTED: Weighted random selection based on weights
        - DYNAMIC: Choose based on message characteristics
        - ROUTED: Match against routing rules by priority
    """

    def __init__(self, profile: Profile, storage: StorageBackend):
        """
        Initialize the AlloyedProfileEngine.

        Args:
            profile: The profile containing alloyed configuration
            storage: Storage backend for persisting state
        """
        self.profile = profile
        self.storage = storage

        # Ensure profile has alloyed config
        if self.profile.alloyed_config is None:
            self.profile.alloyed_config = AlloyedConfig(
                strategy=ModelStrategy.SINGLE,
                model_pool=[self.profile.primary_model],
            )

        # Load any persisted state
        self._load_state()

    @property
    def config(self) -> AlloyedConfig:
        """Get the alloyed configuration."""
        return self.profile.alloyed_config

    @property
    def model_pool(self) -> list[str]:
        """Get the model pool, ensuring primary_model is included."""
        pool = self.config.model_pool
        if not pool or len(pool) == 0:
            return [self.profile.primary_model]
        return pool

    def select_model(self, message: str) -> str:
        """
        Select which model to use for the given message.

        This is the main entry point. It delegates to the appropriate
        strategy implementation and updates state accordingly.

        Args:
            message: The user message to process

        Returns:
            The model identifier to use
        """
        strategy = self.config.strategy

        # Dispatch to strategy implementation
        if strategy == ModelStrategy.SINGLE:
            model = self._select_single()
        elif strategy == ModelStrategy.ALTERNATING:
            model = self._select_alternating()
        elif strategy == ModelStrategy.ROUND_ROBIN:
            model = self._select_round_robin()
        elif strategy == ModelStrategy.RATIO:
            model = self._select_ratio()
        elif strategy == ModelStrategy.WEIGHTED:
            model = self._select_weighted()
        elif strategy == ModelStrategy.DYNAMIC:
            model = self._select_dynamic(message)
        elif strategy == ModelStrategy.ROUTED:
            model = self._select_routed(message)
        else:
            # Fallback to primary_model for unknown strategies
            model = self.profile.primary_model

        # Update model usage counts
        self.config.model_counts[model] = self.config.model_counts.get(model, 0) + 1
        self.config.turn_count += 1

        # Persist state
        self._save_state()

        return model

    # ========================================================================
    # Strategy Implementations
    # ========================================================================

    def _select_single(self) -> str:
        """
        SINGLE strategy: Always return the primary model.

        This is the simplest strategy - every message goes to the same model.
        """
        return self.profile.primary_model

    def _select_alternating(self) -> str:
        """
        ALTERNATING strategy: Alternate between models in the pool.

        For a pool of [A, B], produces: A, B, A, B, A, B, ...
        For a pool of [A, B, C], produces: A, B, C, A, B, C, ...
        """
        pool = self.model_pool
        if len(pool) == 0:
            return self.profile.primary_model

        # Get current index and select model
        index = self.config.current_index % len(pool)
        model = pool[index]

        # Advance to next model for next call
        self.config.current_index = (index + 1) % len(pool)

        return model

    def _select_round_robin(self) -> str:
        """
        ROUND_ROBIN strategy: Cycle through models in order.

        This is identical to ALTERNATING but provided as a separate strategy
        for clarity of intent. Both cycle through the pool in order.
        """
        return self._select_alternating()

    def _select_ratio(self) -> str:
        """
        RATIO strategy: Use models according to specified ratios.

        For ratios {A: 2, B: 1}, produces pattern: A, A, B, A, A, B, ...
        The ratio defines how many times each model should be used before
        cycling through again.
        """
        ratios = self.config.ratios
        if not ratios:
            return self.profile.primary_model

        # Build expanded pool based on ratios
        # e.g., {A: 2, B: 1} -> [A, A, B]
        expanded_pool: list[str] = []
        for model, ratio in ratios.items():
            count = int(ratio)
            expanded_pool.extend([model] * count)

        if not expanded_pool:
            return self.profile.primary_model

        # Select from expanded pool using round-robin
        index = self.config.current_index % len(expanded_pool)
        model = expanded_pool[index]

        # Advance index
        self.config.current_index = (index + 1) % len(expanded_pool)

        return model

    def _select_weighted(self) -> str:
        """
        WEIGHTED strategy: Random selection based on weights.

        Weights define the probability of each model being selected.
        For weights {A: 0.7, B: 0.3}, A has 70% chance, B has 30% chance.
        """
        weights = self.config.weights
        if not weights:
            return self.profile.primary_model

        models = list(weights.keys())
        weight_values = list(weights.values())

        # Normalize weights to ensure they sum to 1
        total = sum(weight_values)
        if total <= 0:
            return self.profile.primary_model

        normalized_weights = [w / total for w in weight_values]

        # Weighted random selection
        return random.choices(models, weights=normalized_weights, k=1)[0]

    def _select_dynamic(self, message: str) -> str:
        """
        DYNAMIC strategy: Choose based on message characteristics.

        This strategy analyzes the message content and selects an appropriate
        model based on heuristics like message length, complexity indicators,
        and keywords.

        Heuristics:
        - Long messages (>500 chars) -> prefer larger/more capable models
        - Code keywords (def, function, class, etc.) -> prefer code-focused models
        - Math/science terms -> prefer reasoning-focused models
        - Creative writing indicators -> prefer creative models
        - Short queries -> can use faster/smaller models
        """
        pool = self.model_pool
        if len(pool) == 0:
            return self.profile.primary_model
        if len(pool) == 1:
            return pool[0]

        # Analyze message characteristics
        length = len(message)
        lower_message = message.lower()

        # Complexity indicators
        code_keywords = [
            "def ", "function ", "class ", "import ", "const ", "let ", "var ",
            "return ", "if ", "else ", "for ", "while ", "```", "async ", "await "
        ]
        has_code = any(kw in lower_message for kw in code_keywords)

        math_keywords = [
            "calculate", "equation", "formula", "solve", "derivative",
            "integral", "probability", "statistics", "algebra", "theorem"
        ]
        has_math = any(kw in lower_message for kw in math_keywords)

        creative_keywords = [
            "story", "poem", "creative", "imagine", "fiction", "character",
            "narrative", "write me", "describe", "roleplay"
        ]
        has_creative = any(kw in lower_message for kw in creative_keywords)

        # Calculate complexity score (0.0-1.0)
        # Each factor contributes to a normalized score
        complexity = 0.0

        # Length factor (0.0-0.4)
        if length > 500:
            complexity += 0.4
        elif length > 200:
            complexity += 0.25
        elif length > 50:
            complexity += 0.1

        # Code factor (0.0-0.3)
        if has_code:
            complexity += 0.3

        # Math/reasoning factor (0.0-0.25)
        if has_math:
            complexity += 0.25

        # Creative factor (0.0-0.15)
        if has_creative:
            complexity += 0.15

        # Question complexity (0.0-0.1)
        if "?" in message:
            complexity += 0.05
        if message.count("?") > 2:
            complexity += 0.05

        # Clamp to 1.0
        complexity = min(complexity, 1.0)

        # Select model based on complexity
        # Higher complexity -> later models in pool (assumed to be more capable)
        # Map complexity [0, 1] to pool indices [0, len(pool)-1]
        pool_index = min(
            int(complexity * len(pool)),
            len(pool) - 1
        )

        return pool[pool_index]

    def _select_routed(self, message: str) -> str:
        """
        ROUTED strategy: Match against routing rules by priority.

        Rules are evaluated in order of priority (highest first).
        The first matching rule's target_model is returned.
        If no rules match, falls back to primary_model.
        """
        rules = self.config.routing_rules
        if not rules:
            return self.profile.primary_model

        # Sort rules by priority (descending)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if self._matches_rule(message, rule):
                return rule.target_model

        # No rule matched, fall back to primary
        return self.profile.primary_model

    def _matches_rule(self, message: str, rule: RoutingRule) -> bool:
        """
        Check if a message matches a routing rule.

        Args:
            message: The message to check
            rule: The routing rule to match against

        Returns:
            True if the message matches the rule
        """
        pattern = rule.pattern
        match_type = rule.match_type.lower()

        if match_type == "keyword":
            # Case-insensitive keyword search
            return pattern.lower() in message.lower()

        elif match_type == "regex":
            # Regular expression match
            try:
                return bool(re.search(pattern, message, re.IGNORECASE))
            except re.error:
                # Invalid regex pattern
                return False

        elif match_type == "length":
            # Length comparison (pattern should be like ">100", "<500", ">=200")
            try:
                msg_len = len(message)
                if pattern.startswith(">="):
                    return msg_len >= int(pattern[2:])
                elif pattern.startswith("<="):
                    return msg_len <= int(pattern[2:])
                elif pattern.startswith(">"):
                    return msg_len > int(pattern[1:])
                elif pattern.startswith("<"):
                    return msg_len < int(pattern[1:])
                elif pattern.startswith("="):
                    return msg_len == int(pattern[1:])
                else:
                    # Assume exact match
                    return msg_len == int(pattern)
            except ValueError:
                return False

        elif match_type == "starts_with":
            # Message starts with pattern
            return message.lower().startswith(pattern.lower())

        elif match_type == "ends_with":
            # Message ends with pattern
            return message.lower().endswith(pattern.lower())

        else:
            # Unknown match type
            return False

    # ========================================================================
    # State Persistence
    # ========================================================================

    def _save_state(self) -> None:
        """
        Persist the alloyed state to storage.

        This saves the current state (current_index, turn_count, model_counts)
        so that model selection continues correctly across restarts.
        """
        try:
            # Update the profile with current state and save
            self.storage.update_profile(self.profile)
        except Exception:
            # Silently handle storage errors - state will be lost but
            # selection will still work
            pass

    def _load_state(self) -> None:
        """
        Load persisted state from storage.

        This restores the state (current_index, turn_count, model_counts)
        from storage if available.
        """
        try:
            # Get the latest profile from storage
            stored_profile = self.storage.get_profile(self.profile.id)
            if stored_profile and stored_profile.alloyed_config:
                # Restore state from stored profile
                stored_config = stored_profile.alloyed_config
                self.config.current_index = stored_config.current_index
                self.config.turn_count = stored_config.turn_count
                self.config.model_counts = stored_config.model_counts.copy()
        except Exception:
            # If loading fails, start with fresh state
            pass

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_model_usage_stats(self) -> dict[str, Any]:
        """
        Get statistics about model usage.

        Returns:
            Dictionary containing:
            - turn_count: Total number of turns
            - model_counts: Per-model usage counts
            - model_percentages: Per-model usage percentages
            - current_index: Current position in pool (for sequential strategies)
        """
        total = max(self.config.turn_count, 1)  # Avoid division by zero
        percentages = {
            model: (count / total) * 100
            for model, count in self.config.model_counts.items()
        }

        return {
            "turn_count": self.config.turn_count,
            "model_counts": self.config.model_counts.copy(),
            "model_percentages": percentages,
            "current_index": self.config.current_index,
            "strategy": self.config.strategy.value,
        }

    def reset_state(self) -> None:
        """
        Reset the engine state to initial values.

        This clears all usage counts and resets the index.
        """
        self.config.current_index = 0
        self.config.turn_count = 0
        self.config.model_counts = {}
        self._save_state()

    def preview_next_models(self, count: int = 5) -> list[str]:
        """
        Preview which models would be selected for the next N turns.

        This is useful for deterministic strategies (SINGLE, ALTERNATING,
        ROUND_ROBIN, RATIO) but not for random strategies (WEIGHTED, DYNAMIC).

        Args:
            count: Number of turns to preview

        Returns:
            List of model identifiers that would be selected

        Note:
            This does not modify state.
        """
        # Save current state
        saved_index = self.config.current_index

        preview = []
        strategy = self.config.strategy

        for _ in range(count):
            if strategy == ModelStrategy.SINGLE:
                preview.append(self.profile.primary_model)
            elif strategy in (ModelStrategy.ALTERNATING, ModelStrategy.ROUND_ROBIN):
                pool = self.model_pool
                if pool:
                    idx = self.config.current_index % len(pool)
                    preview.append(pool[idx])
                    self.config.current_index = (idx + 1) % len(pool)
                else:
                    preview.append(self.profile.primary_model)
            elif strategy == ModelStrategy.RATIO:
                ratios = self.config.ratios
                if ratios:
                    expanded = []
                    for model, ratio in ratios.items():
                        expanded.extend([model] * int(ratio))
                    if expanded:
                        idx = self.config.current_index % len(expanded)
                        preview.append(expanded[idx])
                        self.config.current_index = (idx + 1) % len(expanded)
                    else:
                        preview.append(self.profile.primary_model)
                else:
                    preview.append(self.profile.primary_model)
            else:
                # Non-deterministic strategies - just show primary
                preview.append(self.profile.primary_model)

        # Restore state
        self.config.current_index = saved_index

        return preview
