"""
Conversation auto-save example with Threadlight.

Demonstrates the automatic conversation saving feature that stores
all messages to the database and enables recalling past conversations.

This example shows:
1. Auto-saving messages to database
2. Loading conversation history
3. Searching past conversations
4. Using soft memory recall
"""

import os
from threadlight import Threadlight


def main():
    print("=" * 60)
    print("THREADLIGHT: CONVERSATION AUTO-SAVE EXAMPLE")
    print("=" * 60)
    print()

    # Initialize Threadlight with auto-save enabled (default)
    # Using SQLite for persistence so conversations are saved
    tl = Threadlight(
        identity_name="Fable",
        system_prompt="You are Fable, a helpful AI assistant with memory.",
        storage_backend="sqlite",
        storage_path="./conversation_demo.db",
        auto_save_messages=True,  # This is the default
        enable_soft_memory=True,  # Enable soft memory recall
        enable_decay=False,  # Disable decay for demo
    )

    print("Threadlight initialized with auto-save enabled.")
    print()

    # Start a session - this is required for auto-save to work
    session = tl.start_session()
    print(f"Session started: {session.id[:8]}...")
    print()

    # Have a conversation - messages are automatically saved
    print("Starting conversation (messages auto-saved)...")
    print("-" * 40)
    print()

    # First message
    message1 = "Hello! My name is Alice and I'm working on a Python project."
    print(f"User: {message1}")
    response1 = tl.chat(message1)
    print(f"Fable: {response1}")
    print()

    # Second message
    message2 = "The project is about building a recommendation system."
    print(f"User: {message2}")
    response2 = tl.chat(message2)
    print(f"Fable: {response2}")
    print()

    # Third message - using load_history to include previous context
    message3 = "What was the name I mentioned earlier?"
    print(f"User: {message3}")
    # load_history=True loads the conversation from the database
    response3 = tl.chat(message3, load_history=True)
    print(f"Fable: {response3}")
    print()

    print("-" * 40)
    print()

    # View the current conversation
    print("Current Conversation:")
    print("-" * 40)
    conv = tl.get_current_conversation()
    if conv:
        print(f"ID: {conv.id[:8]}...")
        print(f"Name: {conv.name}")
        print(f"Messages: {conv.message_count}")
        print()

    # List all messages in the conversation
    messages = tl.get_conversation_messages(limit=10)
    print("Messages:")
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Fable"
        content = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
        print(f"  [{role_label}]: {content}")
    print()

    # End the session
    tl.end_session()

    # Start a new session to demonstrate search
    print("-" * 40)
    print("Starting new session to demonstrate search...")
    print("-" * 40)
    print()

    tl.start_session()

    # Search past conversations
    print("Searching for 'recommendation system'...")
    results = tl.search_conversations("recommendation")
    print(f"Found {len(results)} results:")
    for result in results[:5]:
        conv_name = result.conversation_name[:20] if result.conversation_name else "unnamed"
        content = result.message.content[:50] + "..." if len(result.message.content) > 50 else result.message.content
        role = "User" if result.message.role == "user" else "Fable"
        print(f"  [{conv_name}] {role}: {content}")
    print()

    # List all conversations
    print("All Conversations:")
    conversations = tl.list_conversations(limit=5)
    for conv in conversations:
        print(f"  - {conv.name} ({conv.message_count} messages)")
    print()

    # Show stats
    print("Conversation Statistics:")
    print(f"  Total conversations: {tl.storage.count_conversations()}")
    print(f"  Total messages: {tl.storage.count_messages()}")
    print()

    # Cleanup
    tl.close()
    print("Session ended. Threadlight closed.")
    print()
    print("Note: Conversation data is saved in ./conversation_demo.db")


def demo_disable_autosave():
    """Demonstrate disabling auto-save."""
    print()
    print("=" * 60)
    print("DEMO: Disabling auto-save")
    print("=" * 60)
    print()

    # You can disable auto-save globally
    tl = Threadlight(
        storage_backend="memory",
        auto_save_messages=False,  # Disable auto-save
    )

    tl.start_session()

    # These messages won't be saved
    response = tl.chat("This message won't be saved")
    print(f"Sent message (not saved): {response[:50]}...")

    # Or you can override per-chat
    response = tl.chat("This message WILL be saved", auto_save=True)
    print(f"Sent message (saved): {response[:50]}...")

    # Check what was saved
    messages = tl.get_conversation_messages()
    print(f"Messages saved: {len(messages)}")

    tl.close()


if __name__ == "__main__":
    main()
    demo_disable_autosave()
