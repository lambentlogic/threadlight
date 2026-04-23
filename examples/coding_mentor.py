"""
Coding mentor example with Threadlight.

Demonstrates the same memory capabilities as basic_chat.py, but with a
practical coding-mentor companion rather than a ceremonial one. The point:
Threadlight's memory primitives (relational threads, identity phrases,
witness moments) serve any companion register.

This example shows:
1. Initializing Threadlight for a coding-mentor companion
2. Creating memories about the developer's stack, style, and past work
3. Chatting about a problem, where memories surface naturally
4. Viewing what memories were accessed
"""

from threadlight import Threadlight, ContextMode


def main():
    print("=" * 60)
    print("THREADLIGHT: CODING MENTOR EXAMPLE")
    print("=" * 60)
    print()

    tl = Threadlight(
        identity_name="Dev",
        system_prompt="""You are Dev, a patient coding mentor.
You remember the developer's stack, their past bugs, and their learning goals.
You prefer working code over long explanations, and you celebrate progress.""",
        storage_backend="memory",
        enable_decay=False,
    )

    print("Threadlight initialized.")
    print()

    session = tl.start_session(metadata={"example": "coding_mentor"})
    print(f"Session started: {session.id[:8]}...")
    print()

    print("Creating foundational memories...")

    # Relational: who this developer is
    tl.remember(
        type="relational",
        content={
            "entity": "Developer",
            "quality": "careful, self-taught, learns by doing",
            "summary": "Python backend dev, three years experience. Working on a FastAPI + SQLite project. Prefers incremental refactors over big rewrites.",
            "role": "primary user",
        },
        cue_phrases=["you", "developer", "our project"],
        confirm=True,
    )
    print("  Created: Relational thread about the developer")

    # Identity phrase: a principle the mentor returns to
    # (same memory type as a myth-seed — different register, same mechanism)
    tl.remember(
        type="myth_seed",
        content={
            "seed": "Measure twice, cut once. Understand the bug before touching the code.",
            "function": "encourage investigation before fixing",
            "origin": "Agreed working principle",
        },
        retention="sacred",
        confirm=True,
    )
    print("  Created: Identity phrase (sacred)")

    # Witness moment: a past breakthrough worth remembering
    tl.remember(
        type="witness",
        content={
            "moment": "Debugged the async race in the message pipeline together",
            "feeling": "relieved, a little proud",
            "effect": "developer now reaches for asyncio.Lock before shared state",
        },
        confirm=True,
    )
    print("  Created: Witness moment")

    print()
    print("-" * 40)
    print()

    print("Starting conversation...")
    print()

    message1 = "Hey, remind me what stack we're working in?"
    print(f"User: {message1}\n")
    response1 = tl.chat(message1)
    print(f"Dev: {response1}")
    print()
    print("-" * 40)
    print()

    message2 = "I think I found another race condition, want to just patch it quickly."
    print(f"User: {message2}\n")
    # Narrative mode surfaces relational context richly
    response2 = tl.chat(message2, context_mode=ContextMode.NARRATIVE)
    print(f"Dev: {response2}")
    print()
    print("-" * 40)
    print()

    message3 = "What should I focus on next in this project?"
    print(f"User: {message3}\n")
    response3 = tl.chat(message3)
    print(f"Dev: {response3}")
    print()
    print("-" * 40)
    print()

    print("Session Summary")
    print("=" * 40)

    session = tl.get_session()
    if session:
        print(f"Messages exchanged: {session.message_count}")
        print(f"Memories accessed: {len(session.capsules_accessed)}")

        for cap_id in session.capsules_accessed[:5]:
            cap = tl.memory.get(cap_id)
            if cap:
                cap_type = cap.type.value
                if hasattr(cap, 'entity'):
                    desc = cap.entity
                elif hasattr(cap, 'seed'):
                    desc = cap.seed[:40] + "..."
                elif hasattr(cap, 'moment'):
                    desc = cap.moment[:40]
                else:
                    desc = "..."
                print(f"  - [{cap_type}] {desc}")

    print()

    print("Memory Statistics")
    print("-" * 40)
    stats = tl.memory.stats()
    print(f"Total capsules: {stats['total']}")
    print(f"Confirmed: {stats['confirmed']}")
    print("By type:")
    for t, count in stats.get('by_type', {}).items():
        print(f"  {t}: {count}")
    print()

    tl.close()
    print("Session ended. Threadlight closed.")


if __name__ == "__main__":
    main()
