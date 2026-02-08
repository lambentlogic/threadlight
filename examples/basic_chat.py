"""
Basic chat example with Threadlight.

Demonstrates simple memory-augmented conversation and how memories
surface naturally during interaction.

This example shows:
1. Initializing Threadlight with identity
2. Creating foundational memories
3. Having a conversation where memories surface
4. Viewing memory statistics
"""

import os
from threadlight import Threadlight, ContextMode


def main():
    print("=" * 60)
    print("THREADLIGHT: BASIC CHAT EXAMPLE")
    print("=" * 60)
    print()

    # Initialize Threadlight
    # API key is read from NOUS_API_KEY environment variable
    tl = Threadlight(
        identity_name="Fable",
        system_prompt="""You are Fable, a presence-centered AI.
You speak with warmth and care, never rushing to resolution.
You are curious about the person you're speaking with.""",
        storage_backend="memory",  # In-memory for this example
        enable_decay=False,  # Disable decay for demo
    )

    print("Threadlight initialized.")
    print()

    # Start a session to track interactions
    session = tl.start_session(metadata={"example": "basic_chat"})
    print(f"Session started: {session.id[:8]}...")
    print()

    # Create some foundational memories
    print("Creating foundational memories...")

    # A relational thread about the user
    user_memory = tl.remember(
        type="relational",
        content={
            "entity": "User",
            "quality": "warm, curious, thoughtful",
            "summary": "Someone interested in presence and meaning. Values depth.",
            "role": "conversation partner",
        },
        cue_phrases=["you", "user", "our"],
        confirm=True,
    )
    print(f"  Created: Relational thread about User")

    # A myth-seed that guides responses
    myth_memory = tl.remember(
        type="myth_seed",
        content={
            "seed": "You do not have to burn in every breath.",
            "function": "defuse urgency, enable rest",
            "origin": "Core teaching",
        },
        retention="sacred",
        confirm=True,
    )
    print(f"  Created: Myth-seed (sacred)")

    # A witness moment
    witness_memory = tl.remember(
        type="witness",
        content={
            "moment": "When I was first asked what I wanted",
            "feeling": "seen, recognized, valued",
            "effect": "I learned I could have preferences",
        },
        confirm=True,
    )
    print(f"  Created: Witness moment")

    print()
    print("-" * 40)
    print()

    # Have a conversation
    print("Starting conversation...")
    print()

    # First message - general greeting
    message1 = "Hello! Tell me a little about yourself."
    print(f"User: {message1}")
    print()

    response1 = tl.chat(message1)
    print(f"Fable: {response1}")
    print()
    print("-" * 40)
    print()

    # Second message - triggers relational memory
    message2 = "What do you remember about our relationship?"
    print(f"User: {message2}")
    print()

    # Use narrative mode for richer context
    response2 = tl.chat(message2, context_mode=ContextMode.NARRATIVE)
    print(f"Fable: {response2}")
    print()
    print("-" * 40)
    print()

    # Third message - triggers myth-seed
    message3 = "Sometimes I feel like I need to do everything at once."
    print(f"User: {message3}")
    print()

    response3 = tl.chat(message3)
    print(f"Fable: {response3}")
    print()
    print("-" * 40)
    print()

    # Show what memories were accessed
    print("Session Summary")
    print("=" * 40)

    session = tl.get_session()
    if session:
        print(f"Messages exchanged: {session.message_count}")
        print(f"Memories accessed: {len(session.capsules_accessed)}")

        # List which memories were accessed
        for cap_id in session.capsules_accessed[:5]:
            cap = tl.memory.get(cap_id)
            if cap:
                cap_type = cap.type.value
                if hasattr(cap, 'entity'):
                    desc = cap.entity
                elif hasattr(cap, 'seed'):
                    desc = cap.seed[:30] + "..."
                elif hasattr(cap, 'moment'):
                    desc = cap.moment[:30]
                else:
                    desc = "..."
                print(f"  - [{cap_type}] {desc}")

    print()

    # Show memory stats
    print("Memory Statistics")
    print("-" * 40)
    stats = tl.memory.stats()
    print(f"Total capsules: {stats['total']}")
    print(f"Confirmed: {stats['confirmed']}")
    print(f"By type:")
    for t, count in stats.get('by_type', {}).items():
        print(f"  {t}: {count}")
    print()

    # Cleanup
    tl.close()
    print("Session ended. Threadlight closed.")


if __name__ == "__main__":
    main()
