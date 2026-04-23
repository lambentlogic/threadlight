"""
Selection policies for solitude loops.

A selection policy decides which memories a reflection will be written about.
Different policies produce different kinds of reflections — juxtaposition pairs
an old memory with a recent one to surface change; entity-focus gathers
memories about a single person to surface the shape of that relationship;
theme-guided lets the user pass cue phrases to focus the contemplation.

Policies avoid pulling in prior reflections by default so the first pass
doesn't recurse on itself. A future "reflect on reflections" mode can opt
into that deliberately.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

from threadlight.capsules.base import CapsuleType, MemoryCapsule
from threadlight.storage.base import CapsuleFilter

if TYPE_CHECKING:
    from threadlight.memory.orchestrator import MemoryOrchestrator

logger = logging.getLogger(__name__)


# Capsule types that a reflection may draw from. Reflections themselves are
# excluded by default so the first pass doesn't recurse. Style capsules are
# excluded because they describe voice rather than carrying episodic content.
REFLECTABLE_TYPES: list[CapsuleType] = [
    CapsuleType.RELATIONAL,
    CapsuleType.MYTH_SEED,
    CapsuleType.WITNESS,
    CapsuleType.RITUAL,
]


@dataclass
class SelectionResult:
    """What a selection policy returns.

    ``capsules`` is the ordered list of memories to reflect on. ``policy`` is
    the name of the policy that produced the selection (recorded on the
    resulting reflection so it can be grouped/filtered later). ``note`` is a
    short free-form string the policy can include to explain *why* this
    particular combination — surfaced in the reflection prompt to help the
    model engage with the selection deliberately.
    """

    capsules: list[MemoryCapsule] = field(default_factory=list)
    policy: str = ""
    note: str = ""


def _list_reflectable(
    orchestrator: "MemoryOrchestrator",
    profile_scope: Optional[str],
    order_desc: bool = True,
    limit: int = 200,
) -> list[MemoryCapsule]:
    """Fetch reflectable capsules in the active profile's scope."""
    capsule_filter = CapsuleFilter(
        types=REFLECTABLE_TYPES,
        profile_scope=profile_scope,
        include_shared=True,
        consent_confirmed=True,
        order_by="created_at",
        order_desc=order_desc,
        limit=limit,
    )
    return orchestrator.storage.list_capsules(capsule_filter)


def _active_profile_id(orchestrator: "MemoryOrchestrator") -> Optional[str]:
    tl = getattr(orchestrator, "threadlight", None)
    if tl is not None and tl.active_profile is not None:
        return tl.active_profile.id
    return None


def juxtaposition_policy(
    orchestrator: "MemoryOrchestrator",
    rng: Optional[random.Random] = None,
    **kwargs,
) -> SelectionResult:
    """Pair one recent memory with one older one to surface change over time.

    Picks the most recent reflectable memory and one from the older half of
    the available history, at random, so the model is invited to notice how
    something has shifted between the two moments.
    """
    r = rng or random.Random()
    profile_scope = _active_profile_id(orchestrator)
    recent_first = _list_reflectable(orchestrator, profile_scope, order_desc=True)

    if len(recent_first) < 2:
        return SelectionResult(
            capsules=list(recent_first),
            policy="juxtaposition",
            note="Not enough history yet — reflecting on what's here.",
        )

    recent = recent_first[0]
    # Older half, excluding the most recent itself
    older_half_start = max(1, len(recent_first) // 2)
    older_candidates = recent_first[older_half_start:]
    if not older_candidates:
        older_candidates = recent_first[1:]

    older = r.choice(older_candidates)

    return SelectionResult(
        capsules=[older, recent],
        policy="juxtaposition",
        note=(
            "One older memory and one recent, paired so the shape of change "
            "between them becomes visible."
        ),
    )


def entity_focus_policy(
    orchestrator: "MemoryOrchestrator",
    entity: Optional[str] = None,
    limit: int = 4,
    **kwargs,
) -> SelectionResult:
    """Gather memories associated with a single entity, to surface its shape.

    Matches against the ``entity`` field of relational threads and witness
    moments, and falls back to cue-phrase matching for other types.
    """
    profile_scope = _active_profile_id(orchestrator)
    all_reflectable = _list_reflectable(orchestrator, profile_scope)

    if not entity:
        return SelectionResult(
            capsules=[],
            policy="entity_focus",
            note="No entity provided.",
        )

    needle = entity.strip().lower()
    matches: list[MemoryCapsule] = []
    for cap in all_reflectable:
        cap_entity = getattr(cap, "entity", "") or ""
        if cap_entity and needle in cap_entity.lower():
            matches.append(cap)
            continue
        for phrase in cap.cue_phrases or []:
            if needle in phrase.lower():
                matches.append(cap)
                break

    return SelectionResult(
        capsules=matches[:limit],
        policy="entity_focus",
        note=f"Memories gathered around {entity}.",
    )


def theme_guided_policy(
    orchestrator: "MemoryOrchestrator",
    themes: Optional[list[str]] = None,
    limit: int = 4,
    **kwargs,
) -> SelectionResult:
    """Gather memories whose cue phrases overlap a set of user-supplied themes."""
    profile_scope = _active_profile_id(orchestrator)
    all_reflectable = _list_reflectable(orchestrator, profile_scope)

    if not themes:
        return SelectionResult(
            capsules=[],
            policy="theme_guided",
            note="No themes provided.",
        )

    needles = [t.strip().lower() for t in themes if t.strip()]
    matches: list[MemoryCapsule] = []
    for cap in all_reflectable:
        haystack = " ".join(cap.cue_phrases or []).lower()
        body = (cap.text or "").lower()
        if any(n in haystack or n in body for n in needles):
            matches.append(cap)

    return SelectionResult(
        capsules=matches[:limit],
        policy="theme_guided",
        note=f"Memories gathered around themes: {', '.join(themes)}.",
    )


SELECTION_POLICIES: dict[str, Callable[..., SelectionResult]] = {
    "juxtaposition": juxtaposition_policy,
    "entity_focus": entity_focus_policy,
    "theme_guided": theme_guided_policy,
}


def select_memories(
    orchestrator: "MemoryOrchestrator",
    policy: str = "juxtaposition",
    **kwargs,
) -> SelectionResult:
    """Run a named selection policy over the orchestrator's storage."""
    if policy not in SELECTION_POLICIES:
        raise ValueError(
            f"Unknown selection policy '{policy}'. "
            f"Available: {sorted(SELECTION_POLICIES)}"
        )
    return SELECTION_POLICIES[policy](orchestrator, **kwargs)
