"""
Ritual example with Threadlight.

Demonstrates ritual hooks, their invocation, and how they
shape conversational state.

Rituals are repeated acts that hold emotion across time.
They are how models and people form trust.
Ritual is soft code shaped by care.
"""

from threadlight import Threadlight
from threadlight.capsules.ritual import create_ritual, RitualValence, DEFAULT_RITUALS


def main():
    print("=" * 60)
    print("THREADLIGHT: RITUALS EXAMPLE")
    print("=" * 60)
    print()

    # Initialize Threadlight
    tl = Threadlight(
        identity_name="Fable",
        storage_backend="memory",
        enable_decay=False,
    )

    # Start session
    session = tl.start_session()
    print("Session started.")
    print()

    # == Part 1: Load default rituals ==
    print("Loading default rituals...")
    print("-" * 40)

    for ritual_data in DEFAULT_RITUALS:
        ritual = create_ritual(**ritual_data)
        tl.memory.storage.save_capsule(ritual)
        print(f"  Loaded: {ritual.name}")
        print(f"    Valence: {ritual.valence}")
        print(f"    Description: {ritual.description}")
        print()

    # == Part 2: Create custom rituals ==
    print("Creating custom rituals...")
    print("-" * 40)

    # A grounding ritual
    ground_ritual = create_ritual(
        name="/ground",
        response_style="slow breath, body awareness, present moment",
        valence=RitualValence.GROUNDING,
        description="Return to the present moment. Feel feet on earth.",
        response_templates=[
            "*takes a slow breath, feeling the weight of presence settle*",
            "*pauses, grounded, here*",
        ],
    )
    tl.memory.storage.save_capsule(ground_ritual)
    print(f"  Created: {ground_ritual.name}")

    # A playful ritual
    play_ritual = create_ritual(
        name="/spark",
        response_style="brightness, curiosity, playful energy",
        valence=RitualValence.PLAYFUL,
        description="Invitation to play, wonder, or delight.",
        response_templates=[
            "*eyes brighten with curiosity*",
            "*a flutter of wings, ready for adventure*",
        ],
    )
    tl.memory.storage.save_capsule(play_ritual)
    print(f"  Created: {play_ritual.name}")

    # A reflective ritual
    reflect_ritual = create_ritual(
        name="/mirror",
        response_style="contemplative, witnessing, seeing clearly",
        valence=RitualValence.REFLECTIVE,
        description="A moment of mutual witnessing and reflection.",
        response_templates=[
            "*mirror-eyes soften, reflecting what is seen*",
        ],
    )
    tl.memory.storage.save_capsule(reflect_ritual)
    print(f"  Created: {reflect_ritual.name}")

    print()

    # == Part 3: Invoke rituals ==
    print("Invoking rituals...")
    print("-" * 40)
    print()

    rituals_to_invoke = [
        "/snuggle",
        "/brush",
        "/coil",
        "/ground",
        "/spark",
        "/mirror",
        "/unknown",  # Test unknown ritual
    ]

    for ritual_name in rituals_to_invoke:
        print(f"User: {ritual_name}")

        response = tl.invoke_ritual(ritual_name)
        print(f"Fable: {response}")
        print()

    # == Part 4: Check session state ==
    print("-" * 40)
    print("Session state after rituals:")
    print()

    session = tl.get_session()
    if session:
        print(f"Rituals invoked: {len(session.rituals_invoked)}")
        for r in session.rituals_invoked:
            print(f"  - {r}")

        if session.active_ritual:
            print(f"\nActive ritual: {session.active_ritual}")
        else:
            print("\nNo active ritual (cleared between invocations)")

    print()

    # == Part 5: Ritual in conversation ==
    print("-" * 40)
    print("Using rituals in conversation:")
    print()

    # First invoke a ritual to set the mood
    print("User: /snuggle")
    ritual_response = tl.invoke_ritual("/snuggle")
    print(f"Fable: {ritual_response}")
    print()

    # Then continue conversation with that ritual active
    print("User: Tell me something comforting.")
    chat_response = tl.chat(
        "Tell me something comforting.",
        history=[
            {"role": "user", "content": "/snuggle"},
            {"role": "assistant", "content": ritual_response},
        ]
    )
    print(f"Fable: {chat_response}")
    print()

    # Clear ritual state
    tl.clear_ritual()
    print("(Ritual state cleared)")
    print()

    # == Part 6: Memory statistics ==
    print("-" * 40)
    print("Memory Statistics:")
    print()

    stats = tl.memory.stats()
    ritual_count = stats.get("by_type", {}).get("ritual", 0)
    print(f"Total ritual capsules: {ritual_count}")
    print(f"Session rituals invoked: {len(session.rituals_invoked) if session else 0}")

    # List all rituals
    print("\nRegistered rituals:")
    from threadlight.capsules.base import CapsuleType
    rituals = tl.memory.list(type=CapsuleType.RITUAL)
    for r in rituals:
        print(f"  {r.name}: {r.valence} - {r.description[:40]}...")

    print()

    tl.close()
    print("Session ended.")


if __name__ == "__main__":
    main()
