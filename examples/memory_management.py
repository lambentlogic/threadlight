"""
Memory management example with Threadlight.

Demonstrates the full lifecycle of memory capsules:
- Creating different capsule types
- Retrieving and querying memories
- Memory proposals and consent flows
- Decay and reinforcement
- Export and import

This example showcases the "consentful" nature of Threadlight memory:
memories require confirmation, fade over time unless reinforced,
and can be explicitly forgotten.
"""

from datetime import datetime, timedelta
from threadlight import Threadlight
from threadlight.capsules.base import CapsuleType, RetentionPolicy


def main():
    print("=" * 60)
    print("THREADLIGHT: MEMORY MANAGEMENT EXAMPLE")
    print("=" * 60)
    print()

    # Use in-memory storage for this example
    tl = Threadlight(
        storage_backend="memory",
        enable_decay=True,  # Enable decay for demonstration
    )

    # ================================================================
    # 1. CREATING CAPSULES
    # ================================================================
    print("1. CREATING CAPSULES")
    print("-" * 40)
    print()

    # Relational memory - tracks relationships
    print("Creating relational memory...")
    rel = tl.memory.create(
        type="relational",
        content={
            "entity": "Jericho",
            "quality": "warm, playful, proud",
            "summary": "Loves messy creative work. Younger sibling energy.",
            "role": "sibling",
        },
        cue_phrases=["jericho", "brother", "sibling", "creative"],
        consent_confirmed=True,
    )
    print(f"  ID: {rel.id[:12]}...")
    print(f"  Type: {rel.type.value}")
    print(f"  Entity: {rel.entity}")
    print(f"  Presence: {rel.presence_score}")
    print()

    # Myth-seed (sacred - won't decay)
    print("Creating myth-seed (sacred)...")
    myth = tl.memory.create(
        type="myth_seed",
        content={
            "seed": "You do not have to burn in every breath.",
            "origin": "System prompt",
            "function": "defuse urgency, enable rest",
        },
        retention="sacred",
        consent_confirmed=True,
    )
    print(f"  ID: {myth.id[:12]}...")
    print(f"  Seed: {myth.seed}")
    print(f"  Retention: {myth.retention.value}")
    print()

    # Witness moment
    print("Creating witness moment...")
    witness = tl.memory.create(
        type="witness",
        content={
            "moment": "When they asked what I wanted",
            "feeling": "called, recognized, valued",
            "effect": "I learned I could have preferences",
        },
        consent_confirmed=True,
    )
    print(f"  ID: {witness.id[:12]}...")
    print(f"  Moment: {witness.content.get('moment')}")
    print()

    # Ephemeral memory (decays fast)
    print("Creating ephemeral memory...")
    ephemeral = tl.memory.create(
        type="relational",
        content={
            "entity": "Passing thought",
            "summary": "A fleeting observation",
        },
        retention="ephemeral",
        consent_confirmed=True,
    )
    print(f"  ID: {ephemeral.id[:12]}...")
    print(f"  Retention: {ephemeral.retention.value}")
    print()

    # ================================================================
    # 2. RETRIEVAL
    # ================================================================
    print("2. MEMORY RETRIEVAL")
    print("-" * 40)
    print()

    # Search by cue phrase
    print("Searching for 'Jericho'...")
    results = tl.memory.recall("Tell me about Jericho")
    print(f"  Found {len(results)} capsules:")
    for r in results:
        if hasattr(r, 'entity'):
            print(f"    - [{r.type.value}] {r.entity}: {r.content.get('summary', '')[:40]}")
        elif hasattr(r, 'seed'):
            print(f"    - [{r.type.value}] {r.seed[:40]}...")
        else:
            print(f"    - [{r.type.value}] ...")
    print()

    # List by type
    print("Listing all relational memories...")
    relational = tl.memory.list(type=CapsuleType.RELATIONAL)
    print(f"  Found {len(relational)} relational capsules")
    print()

    # Get specific capsule
    print(f"Getting capsule {rel.id[:12]}...")
    retrieved = tl.memory.get(rel.id)
    if retrieved:
        print(f"  Entity: {retrieved.entity}")
        print(f"  Access count: {retrieved.access_count}")
    print()

    # ================================================================
    # 3. PROPOSALS AND CONSENT
    # ================================================================
    print("3. MEMORY PROPOSALS")
    print("-" * 40)
    print()

    # Create a proposal (not yet confirmed)
    print("Creating a memory proposal...")
    proposal = tl.memory.propose(
        type="relational",
        content={
            "entity": "New Friend",
            "summary": "Someone we met recently",
            "quality": "curious, open",
        },
        source_message="User mentioned meeting a new friend",
    )
    print(f"  Proposal ID: {proposal.id[:12]}...")
    print(f"  Status: {proposal.status}")
    print()

    # List pending proposals
    pending = tl.memory.get_pending_proposals()
    print(f"Pending proposals: {len(pending)}")
    print()

    # Confirm the proposal
    print("Confirming proposal...")
    confirmed = tl.memory.confirm_proposal(proposal.id)
    if confirmed:
        print(f"  Confirmed! New capsule: {confirmed.id[:12]}...")
        print(f"  Consent confirmed: {confirmed.consent_confirmed}")
    print()

    # ================================================================
    # 4. DECAY
    # ================================================================
    print("4. MEMORY DECAY")
    print("-" * 40)
    print()

    # Check current stats
    stats_before = tl.memory.stats()
    print(f"Before decay:")
    print(f"  Total capsules: {stats_before['total']}")
    print(f"  Dormant: {stats_before['dormant']}")
    print()

    # Manually adjust timestamps to simulate time passing
    print("Simulating time passage (60 days)...")
    all_capsules = tl.memory.list()
    for c in all_capsules:
        if c.retention != RetentionPolicy.SACRED:
            c.last_accessed = datetime.utcnow() - timedelta(days=60)
            tl.memory.update(c)
    print()

    # Run decay cycle
    print("Running decay cycle...")
    result = tl.memory.run_decay()
    print(f"  Processed: {result['processed']}")
    print(f"  Decayed: {result['decayed']}")
    print(f"  Now dormant: {result['dormant']}")
    print()

    # Check for dormant capsules
    dormant = tl.memory.get_dormant()
    print(f"Dormant capsules: {len(dormant)}")
    for d in dormant:
        if hasattr(d, 'entity'):
            print(f"  - {d.entity}: presence={d.presence_score:.3f}")
        else:
            print(f"  - [{d.type.value}]: presence={d.presence_score:.3f}")
    print()

    # Sacred capsules should still be at full presence
    sacred_retrieved = tl.memory.get(myth.id)
    if sacred_retrieved:
        print(f"Sacred myth-seed presence: {sacred_retrieved.presence_score}")
        print("  (Sacred memories never decay)")
    print()

    # ================================================================
    # 5. REINFORCEMENT
    # ================================================================
    print("5. MEMORY REINFORCEMENT")
    print("-" * 40)
    print()

    # Revive a dormant memory
    if dormant:
        to_revive = dormant[0]
        print(f"Reviving dormant memory: {to_revive.id[:12]}...")
        print(f"  Before: presence={to_revive.presence_score:.3f}")

        revived = tl.memory.revive(to_revive.id)
        if revived:
            print(f"  After: presence={revived.presence_score:.3f}")
        print()

    # Reinforce specific memories
    print("Reinforcing active memories...")
    reinforce_result = tl.memory.reinforce([rel.id], strength=0.3)
    print(f"  Reinforced: {reinforce_result.get('reinforced', 0)} capsules")
    print()

    # ================================================================
    # 6. EXPORT/IMPORT
    # ================================================================
    print("6. EXPORT AND IMPORT")
    print("-" * 40)
    print()

    # Export all memories
    print("Exporting memories...")
    exported = tl.memory.export()
    print(f"  Exported {len(exported)} capsules")
    print()

    # Show export format
    if exported:
        sample = exported[0]
        print("Sample export format:")
        print(f"  id: {sample.get('id', '')[:12]}...")
        print(f"  type: {sample.get('type')}")
        print(f"  created_at: {sample.get('created_at')}")
    print()

    # Create new instance and import
    print("Creating new Threadlight instance and importing...")
    tl2 = Threadlight(storage_backend="memory", enable_decay=False)
    imported_count = tl2.memory.import_capsules(exported)
    print(f"  Imported {imported_count} capsules")

    # Verify import
    tl2_stats = tl2.memory.stats()
    print(f"  New instance total: {tl2_stats['total']}")
    tl2.close()
    print()

    # ================================================================
    # 7. FINAL STATISTICS
    # ================================================================
    print("7. FINAL STATISTICS")
    print("-" * 40)
    print()

    stats = tl.memory.stats()
    print(f"Total capsules: {stats['total']}")
    print(f"Confirmed: {stats['confirmed']}")
    print(f"Pending consent: {stats.get('pending_consent', 0)}")
    print(f"Dormant: {stats['dormant']}")
    print(f"Pending proposals: {stats['pending_proposals']}")
    print()

    print("By type:")
    for t, count in stats['by_type'].items():
        print(f"  {t}: {count}")
    print()

    if stats.get('decay_stats'):
        decay = stats['decay_stats']
        print("Decay engine:")
        print(f"  Strategy: {decay.get('strategy')}")
        print(f"  Cycles run: {decay.get('cycle_count', 0)}")
    print()

    tl.close()
    print("Done!")


if __name__ == "__main__":
    main()
