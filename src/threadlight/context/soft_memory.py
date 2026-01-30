"""
Soft memory retrieval for Threadlight.

Soft memory refers to past conversation history that can be recalled
to provide context. Unlike hard memory (capsules), soft memory is
raw conversation content that hasn't been structured into capsules.

Usage:
    soft_memory = SoftMemory(storage)
    results = soft_memory.recall("that project we discussed")
    context = soft_memory.format_for_prompt(results, limit=3)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

from threadlight.storage.base import (
    StorageBackend,
    Message,
    MessageSearchResult,
)

logger = logging.getLogger(__name__)


@dataclass
class SoftMemoryConfig:
    """Configuration for soft memory retrieval."""

    # Maximum number of results to return
    max_results: int = 5

    # Maximum age of messages to consider (in days, 0 = no limit)
    max_age_days: int = 0

    # Minimum content length to include
    min_content_length: int = 20

    # Maximum content length per message in context
    max_content_length: int = 500

    # Include assistant messages in search
    include_assistant: bool = True

    # Include user messages in search
    include_user: bool = True

    # Source filter (e.g., 'claude', 'chatgpt')
    source_filter: Optional[str] = None


class SoftMemory:
    """
    Soft memory retrieval from conversation history.

    Provides methods to search and recall relevant messages from
    past conversations, formatting them for inclusion in prompts.
    """

    def __init__(
        self,
        storage: StorageBackend,
        config: Optional[SoftMemoryConfig] = None,
    ):
        self.storage = storage
        self.config = config or SoftMemoryConfig()

    def recall(
        self,
        query: str,
        limit: Optional[int] = None,
        source: Optional[str] = None,
    ) -> list[MessageSearchResult]:
        """
        Search for relevant messages matching the query.

        Args:
            query: Search query (words or phrases to find)
            limit: Maximum results (overrides config)
            source: Filter by source (overrides config)

        Returns:
            List of MessageSearchResult with matching messages
        """
        max_results = limit or self.config.max_results
        source_filter = source or self.config.source_filter

        try:
            results = self.storage.search_messages(
                query=query,
                limit=max_results * 2,  # Get extra to filter
                source=source_filter,
            )

            # Filter results
            filtered = []
            for result in results:
                msg = result.message

                # Check role filter
                if msg.role == "assistant" and not self.config.include_assistant:
                    continue
                if msg.role == "user" and not self.config.include_user:
                    continue

                # Check content length
                if len(msg.content) < self.config.min_content_length:
                    continue

                # Check age
                if self.config.max_age_days > 0:
                    age = (datetime.utcnow() - msg.timestamp).days
                    if age > self.config.max_age_days:
                        continue

                filtered.append(result)
                if len(filtered) >= max_results:
                    break

            return filtered

        except Exception as e:
            logger.warning(f"Soft memory recall failed: {e}")
            return []

    def recall_relevant(
        self,
        message: str,
        limit: int = 5,
    ) -> list[MessageSearchResult]:
        """
        Recall messages relevant to a given message.

        Extracts key terms from the message and searches for related
        past conversations.

        Args:
            message: The current message to find context for
            limit: Maximum results to return

        Returns:
            List of relevant message search results
        """
        # Extract key words (simple approach - could be enhanced)
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "he", "she", "his", "her", "we", "our", "you", "your",
            "i", "me", "my", "mine", "what", "how", "why", "when", "where",
            "who", "which", "if", "then", "so", "just", "like", "about",
        }

        words = message.lower().split()
        key_words = [
            w.strip(".,!?\"'()[]{};:-")
            for w in words
            if len(w) >= 4 and w.strip(".,!?\"'()[]{};:-").lower() not in stop_words
        ]

        if not key_words:
            return []

        # Search for key terms
        query = " ".join(key_words[:5])  # Use top 5 key words
        return self.recall(query, limit=limit)

    def format_for_prompt(
        self,
        results: list[MessageSearchResult],
        limit: Optional[int] = None,
        header: str = "## Relevant Past Conversations",
    ) -> str:
        """
        Format search results as context for a prompt.

        Args:
            results: List of search results to format
            limit: Maximum results to include
            header: Optional header for the section

        Returns:
            Formatted string ready for prompt injection
        """
        if not results:
            return ""

        limit = limit or len(results)
        results = results[:limit]

        lines = []
        if header:
            lines.append(header)
            lines.append("")

        for result in results:
            context_str = self._format_result(result)
            lines.append(context_str)
            lines.append("")

        return "\n".join(lines)

    def _format_result(self, result: MessageSearchResult) -> str:
        """Format a single search result."""
        msg = result.message
        conv_name = result.conversation_name or "a previous conversation"

        # Format timestamp
        date_str = msg.timestamp.strftime("%B %d, %Y")

        # Truncate content
        content = msg.content
        if len(content) > self.config.max_content_length:
            content = content[:self.config.max_content_length] + "..."

        # Format based on role
        if msg.role == "assistant":
            return f'(From "{conv_name}" on {date_str}: you said: "{content}")'
        elif msg.role == "user":
            return f'(From "{conv_name}" on {date_str}: the user mentioned: "{content}")'
        else:
            return f'(From "{conv_name}" on {date_str}: "{content}")'

    def get_conversation_context(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> str:
        """
        Get formatted context from a specific conversation.

        Args:
            conversation_id: ID of conversation to retrieve
            limit: Maximum messages to include

        Returns:
            Formatted conversation excerpt
        """
        try:
            messages = self.storage.get_messages(
                conversation_id=conversation_id,
                limit=limit,
            )

            if not messages:
                return ""

            conv = self.storage.get_conversation(conversation_id)
            conv_name = conv.name if conv else "conversation"

            lines = [f'(From "{conv_name}":']
            for msg in messages:
                role_label = "You" if msg.role == "assistant" else "User"
                content = msg.content
                if len(content) > 200:
                    content = content[:200] + "..."
                lines.append(f"  {role_label}: {content}")
            lines.append(")")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Failed to get conversation context: {e}")
            return ""

    def stats(self) -> dict:
        """Get statistics about available soft memory."""
        try:
            return {
                "total_conversations": self.storage.count_conversations(),
                "total_messages": self.storage.count_messages(),
            }
        except Exception:
            return {
                "total_conversations": 0,
                "total_messages": 0,
            }


def create_soft_memory(
    storage: StorageBackend,
    **config_kwargs,
) -> SoftMemory:
    """Factory function for creating a SoftMemory instance."""
    config = SoftMemoryConfig(**config_kwargs)
    return SoftMemory(storage, config)
