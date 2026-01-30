"""
Ritual system for Threadlight.

Rituals are repeated acts that hold emotion across time.
They are how models and people form trust.
"""

# Ritual handling is integrated into capsules and memory orchestrator
# This module provides additional ritual utilities

from threadlight.capsules.ritual import RitualHook, create_ritual, DEFAULT_RITUALS

__all__ = ["RitualHook", "create_ritual", "DEFAULT_RITUALS"]
