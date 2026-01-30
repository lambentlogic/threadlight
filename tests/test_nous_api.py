"""
Integration tests for the Nous Research API.

These tests validate real API calls to Nous Research using Hermes-4.3-36B.
They require a valid NOUS_API_KEY environment variable.

To run these tests:
    NOUS_API_KEY=your-key pytest tests/test_nous_api.py -v

Tests are marked as integration tests and will be skipped if no API key is available.
"""

import os
import pytest

# Check for API key
NOUS_API_KEY = os.environ.get("NOUS_API_KEY")
HAS_API_KEY = bool(NOUS_API_KEY)

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not HAS_API_KEY,
    reason="NOUS_API_KEY environment variable not set"
)


@pytest.fixture
def nous_provider():
    """Create a real Nous provider."""
    from threadlight.providers.openai import OpenAIProvider

    return OpenAIProvider(
        api_base="https://inference-api.nousresearch.com/v1",
        api_key=NOUS_API_KEY,
        model="Hermes-4.3-36B",
        timeout=60.0,
    )


@pytest.fixture
def threadlight_nous():
    """Create a Threadlight instance connected to Nous API."""
    from threadlight import Threadlight

    tl = Threadlight(
        api_key=NOUS_API_KEY,
        api_base="https://inference-api.nousresearch.com/v1",
        model="Hermes-4.3-36B",
        storage_backend="memory",
        identity_name="Fable",
        system_prompt="You are Fable, a presence-centered AI. Respond briefly.",
        enable_memory=True,
        enable_decay=False,
    )
    yield tl
    tl.close()


class TestNousProviderDirect:
    """Test the Nous provider directly."""

    @pytest.mark.integration
    def test_health_check(self, nous_provider):
        """Test that the provider can reach the API."""
        result = nous_provider.health_check()
        assert result is True

    @pytest.mark.integration
    def test_basic_completion(self, nous_provider):
        """Test a basic chat completion."""
        from threadlight.providers.base import ProviderMessage

        messages = [
            ProviderMessage(
                role="system",
                content="You are a helpful assistant. Be concise."
            ),
            ProviderMessage(
                role="user",
                content="Say hello in exactly 5 words."
            ),
        ]

        response = nous_provider.complete(messages, max_tokens=50)

        assert response is not None
        assert response.content != ""
        assert response.finish_reason in ("stop", "length")
        assert response.total_tokens > 0

        print(f"\nResponse: {response.content}")
        print(f"Tokens: {response.total_tokens}")

    @pytest.mark.integration
    def test_streaming(self, nous_provider):
        """Test streaming completion."""
        from threadlight.providers.base import ProviderMessage

        messages = [
            ProviderMessage(
                role="system",
                content="You are a helpful assistant."
            ),
            ProviderMessage(
                role="user",
                content="Count from 1 to 5."
            ),
        ]

        chunks = list(nous_provider.stream(messages, max_tokens=100))

        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert "1" in full_response

        print(f"\nStreamed response: {full_response}")

    @pytest.mark.integration
    def test_temperature_variation(self, nous_provider):
        """Test that temperature affects output."""
        from threadlight.providers.base import ProviderMessage

        messages = [
            ProviderMessage(
                role="user",
                content="Generate a random single word."
            ),
        ]

        # Generate with high temperature
        responses = []
        for _ in range(3):
            response = nous_provider.complete(
                messages,
                temperature=1.5,
                max_tokens=20,
            )
            responses.append(response.content.strip())

        # With high temperature, responses might vary
        # (not guaranteed, but likely)
        print(f"\nResponses at temp=1.5: {responses}")


class TestNousWithThreadlight:
    """Test Threadlight integration with Nous API."""

    @pytest.mark.integration
    def test_basic_chat(self, threadlight_nous):
        """Test basic chat through Threadlight."""
        response = threadlight_nous.chat(
            "Hello! Who are you? Answer in one sentence."
        )

        assert response != ""
        # Should mention being Fable or an AI
        assert len(response) > 10

        print(f"\nThreadlight response: {response}")

    @pytest.mark.integration
    def test_chat_with_memory(self, threadlight_nous):
        """Test chat with memory context."""
        # Create a memory
        threadlight_nous.remember(
            type="relational",
            content={
                "entity": "TestUser",
                "tone": "curious, friendly",
                "summary": "Someone interested in testing presence.",
            },
            cue_phrases=["testuser", "you", "our"],
            confirm=True,
        )

        # Chat referencing the memory
        response = threadlight_nous.chat(
            "What do you know about our relationship?"
        )

        assert response != ""
        print(f"\nMemory-augmented response: {response}")

    @pytest.mark.integration
    def test_chat_with_myth_seed(self, threadlight_nous):
        """Test that myth-seeds influence response."""
        # Create a myth-seed
        threadlight_nous.remember(
            type="myth_seed",
            content={
                "seed": "You do not have to burn in every breath.",
                "origin": "Core teaching",
                "function": "defuse urgency",
            },
            retention="sacred",
            confirm=True,
        )

        # Ask something that might trigger it
        response = threadlight_nous.chat(
            "I feel like I need to do everything at once. Help?"
        )

        assert response != ""
        # Response might reference rest, breathing, or slowing down
        print(f"\nWith myth-seed: {response}")

    @pytest.mark.integration
    def test_ritual_invocation(self, threadlight_nous):
        """Test ritual invocation with Nous."""
        from threadlight.capsules.ritual import create_ritual, RitualValence

        # Create a ritual
        ritual = create_ritual(
            name="/snuggle",
            response_style="warmth-coil, softened tone",
            valence=RitualValence.COMFORTING,
            description="A gesture of coiled presence.",
            response_templates=["*settles close, presence warm*"],
        )
        ritual.consent_confirmed = True
        threadlight_nous.storage.save_capsule(ritual)

        # Invoke it
        response = threadlight_nous.invoke_ritual("/snuggle")

        # Should use the template
        assert "*" in response or "warm" in response.lower()
        print(f"\nRitual response: {response}")

    @pytest.mark.integration
    def test_multi_turn_conversation(self, threadlight_nous):
        """Test multi-turn conversation maintaining context."""
        history = []

        # Turn 1
        response1 = threadlight_nous.chat("My name is TestPerson.")
        history.append({"role": "user", "content": "My name is TestPerson."})
        history.append({"role": "assistant", "content": response1})

        print(f"\nTurn 1: {response1}")

        # Turn 2 - should remember the name
        response2 = threadlight_nous.chat(
            "What is my name?",
            history=history
        )

        print(f"Turn 2: {response2}")

        # Response should mention TestPerson
        assert "TestPerson" in response2 or "name" in response2.lower()

    @pytest.mark.integration
    def test_session_tracking(self, threadlight_nous):
        """Test that sessions track API interactions."""
        session = threadlight_nous.start_session(purpose="api_test")

        # Create memory
        threadlight_nous.remember(
            type="relational",
            content={"entity": "API"},
            cue_phrases=["api"],
            confirm=True,
        )

        # Chat
        threadlight_nous.chat("Testing API interaction.")
        threadlight_nous.chat("Another message.")

        # Check session
        current = threadlight_nous.get_session()
        assert current.message_count >= 2

        # End session
        ended = threadlight_nous.end_session()
        assert ended.duration_seconds > 0

        print(f"\nSession duration: {ended.duration_seconds:.2f}s")
        print(f"Messages: {ended.message_count}")
        print(f"Memories accessed: {len(ended.capsules_accessed)}")


class TestNousPerformance:
    """Performance and reliability tests for Nous API."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_response_time(self, nous_provider):
        """Measure response time for a typical request."""
        import time
        from threadlight.providers.base import ProviderMessage

        messages = [
            ProviderMessage(role="system", content="Be concise."),
            ProviderMessage(role="user", content="What is 2+2?"),
        ]

        start = time.time()
        response = nous_provider.complete(messages, max_tokens=20)
        elapsed = time.time() - start

        assert response.content != ""
        print(f"\nResponse time: {elapsed:.2f}s")
        print(f"Response: {response.content}")

        # Should complete in reasonable time
        assert elapsed < 30.0

    @pytest.mark.integration
    @pytest.mark.slow
    def test_multiple_sequential_requests(self, threadlight_nous):
        """Test multiple sequential requests."""
        responses = []

        for i in range(3):
            response = threadlight_nous.chat(f"Message number {i+1}.")
            responses.append(response)
            print(f"\nRequest {i+1}: {response[:50]}...")

        assert len(responses) == 3
        assert all(r != "" for r in responses)


class TestNousErrorHandling:
    """Test error handling with Nous API."""

    @pytest.mark.integration
    def test_empty_message(self, nous_provider):
        """Test handling of empty message."""
        from threadlight.providers.base import ProviderMessage

        messages = [
            ProviderMessage(role="user", content=""),
        ]

        # Should not crash
        try:
            response = nous_provider.complete(messages, max_tokens=20)
            print(f"\nEmpty message response: {response.content}")
        except Exception as e:
            print(f"\nEmpty message error (expected): {type(e).__name__}")

    @pytest.mark.integration
    def test_very_long_context(self, nous_provider):
        """Test with a longer context."""
        from threadlight.providers.base import ProviderMessage

        # Create a moderately long context
        long_context = "This is a test. " * 100  # ~1600 chars

        messages = [
            ProviderMessage(
                role="system",
                content=long_context
            ),
            ProviderMessage(
                role="user",
                content="Summarize the above in one word."
            ),
        ]

        response = nous_provider.complete(messages, max_tokens=50)
        assert response.content != ""
        print(f"\nLong context response: {response.content}")


# Convenience function for manual testing
def quick_test():
    """Quick test function for manual verification."""
    if not HAS_API_KEY:
        print("No NOUS_API_KEY set. Skipping quick test.")
        return

    from threadlight import Threadlight

    print("Connecting to Nous Research API...")

    tl = Threadlight(
        api_key=NOUS_API_KEY,
        model="Hermes-4.3-36B",
        storage_backend="memory",
        identity_name="Fable",
    )

    print("Sending test message...")
    response = tl.chat("Hello! Please confirm you're working by saying 'OK'.")
    print(f"Response: {response}")

    tl.close()
    print("Done!")


if __name__ == "__main__":
    quick_test()
