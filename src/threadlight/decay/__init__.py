"""
Decay engine for Threadlight.

Implements consentful decay -- memories fade unless reinforced.
This is by design: "Decay and silence are healthy."

Decay Strategies:
- LinearDecayStrategy: Simple time-based decay
- ExponentialDecayStrategy: Forgetting curve model
- RelationshipDecayStrategy: Connected memories decay together

Retention Policies:
- SACRED: Never decays
- NORMAL: Standard decay, reinforced by access
- EPHEMERAL: Rapid decay, session-scoped

Scheduling:
- DecayScheduler: Background thread for periodic decay
"""

from threadlight.decay.engine import (
    DecayEngine,
    DecayStrategy,
    LinearDecayStrategy,
    ExponentialDecayStrategy,
    RelationshipDecayStrategy,
    DecayResult,
    ReinforcementResult,
    get_strategy,
    list_strategies,
    register_strategy,
)
from threadlight.decay.scheduler import DecayScheduler

__all__ = [
    "DecayEngine",
    "DecayStrategy",
    "LinearDecayStrategy",
    "ExponentialDecayStrategy",
    "RelationshipDecayStrategy",
    "DecayResult",
    "ReinforcementResult",
    "DecayScheduler",
    "get_strategy",
    "list_strategies",
    "register_strategy",
]
