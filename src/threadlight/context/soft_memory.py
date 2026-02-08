"""
Soft memory retrieval for Threadlight.

Soft memory refers to past conversation history that can be recalled
to provide context. Unlike hard memory (capsules), soft memory is
raw conversation content that hasn't been structured into capsules.

This module also provides integrated recall that weaves soft memory
(past conversations) with hard memory (capsules) to create connected
context. When a conversation mentions a person, integrated recall
surfaces both the conversation and the relational thread about them.

Usage:
    soft_memory = SoftMemory(storage)
    results = soft_memory.recall("that project we discussed")
    context = soft_memory.format_for_prompt(results, limit=3)

    # Integrated recall with capsules
    woven = soft_memory.recall_with_context("Remember Sarah?", orchestrator)
    print(woven.format_for_prompt())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import logging
import re

from threadlight.storage.base import (
    StorageBackend,
    Message,
    MessageSearchResult,
)

if TYPE_CHECKING:
    from threadlight.capsules.base import MemoryCapsule
    from threadlight.memory.orchestrator import MemoryOrchestrator

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


@dataclass
class EntityMatch:
    """An entity extracted from text with its source context."""

    name: str  # The entity name (e.g., "Sarah", "Project Alpha")
    source_text: str  # The text it was extracted from
    confidence: float = 1.0  # Confidence score (1.0 for exact matches)

    def __hash__(self) -> int:
        return hash(self.name.lower())

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, EntityMatch):
            return False
        return self.name.lower() == other.name.lower()


@dataclass
class WovenMemory:
    """
    Integrated memory combining soft (conversations) and hard (capsules) memory.

    This represents the "threads" vision - memories connect across time and type.
    When past conversations mention people or topics, the related capsules
    surface to provide relational context.

    Example:
        # User asks about "that time with Sarah"
        # WovenMemory contains:
        # - soft_memory_results: past conversations mentioning Sarah
        # - related_capsules: relational thread about who Sarah is
        # - entity_capsule_map: {"Sarah": [RelationalThread capsule]}
    """

    # Past conversation messages that were recalled
    soft_memory_results: list[MessageSearchResult] = field(default_factory=list)

    # Capsules related to entities found in soft memory
    related_capsules: list['MemoryCapsule'] = field(default_factory=list)

    # Mapping of entity names to their related capsules
    entity_capsule_map: dict[str, list['MemoryCapsule']] = field(default_factory=dict)

    # Entities that were extracted but had no matching capsules
    unmatched_entities: list[str] = field(default_factory=list)

    def has_woven_context(self) -> bool:
        """Check if there is both soft memory and related capsules."""
        return bool(self.soft_memory_results and self.related_capsules)

    def format_for_prompt(
        self,
        max_soft_memory: int = 3,
        max_capsules_per_entity: int = 2,
        header: str = "## Relevant Context",
    ) -> str:
        """
        Format woven memory as context for a prompt.

        Creates a unified context that weaves together past conversations
        with relational information about mentioned entities.

        Args:
            max_soft_memory: Maximum past conversation excerpts
            max_capsules_per_entity: Maximum capsules per entity
            header: Section header

        Returns:
            Formatted context string
        """
        if not self.soft_memory_results and not self.related_capsules:
            return ""

        lines = []
        if header:
            lines.append(header)
            lines.append("")

        # Format soft memory results with integrated capsule context
        for i, result in enumerate(self.soft_memory_results[:max_soft_memory]):
            # Format the conversation excerpt
            msg = result.message
            conv_name = result.conversation_name or "a previous conversation"
            date_str = msg.timestamp.strftime("%B %d, %Y")

            content = msg.content
            if len(content) > 400:
                content = content[:400] + "..."

            if msg.role == "assistant":
                lines.append(f'(From "{conv_name}" on {date_str}: you said: "{content}")')
            else:
                lines.append(f'(From "{conv_name}" on {date_str}: the user mentioned: "{content}")')

            # Find entities mentioned in this message and add their context
            mentioned_entities = self._find_entities_in_text(content)
            for entity in mentioned_entities:
                if entity in self.entity_capsule_map:
                    capsules = self.entity_capsule_map[entity][:max_capsules_per_entity]
                    for capsule in capsules:
                        # Add relational context inline
                        if hasattr(capsule, 'summary') and hasattr(capsule, 'quality'):
                            quality_phrase = f" (quality: {capsule.quality})" if capsule.quality else ""
                            lines.append(f"  -> About {entity}: {capsule.summary}{quality_phrase}")
                        elif hasattr(capsule, 'content'):
                            summary = capsule.content.get('summary', str(capsule.content)[:100])
                            lines.append(f"  -> About {entity}: {summary}")

            lines.append("")

        # Add any capsules for entities not yet mentioned
        shown_entities = set()
        for result in self.soft_memory_results[:max_soft_memory]:
            content = result.message.content
            shown_entities.update(self._find_entities_in_text(content))

        remaining_entities = set(self.entity_capsule_map.keys()) - shown_entities
        if remaining_entities:
            lines.append("### Related Context")
            for entity in remaining_entities:
                capsules = self.entity_capsule_map[entity][:max_capsules_per_entity]
                for capsule in capsules:
                    if hasattr(capsule, 'summary'):
                        lines.append(f"(About {entity}: {capsule.summary})")
            lines.append("")

        return "\n".join(lines).strip()

    def _find_entities_in_text(self, text: str) -> set[str]:
        """Find which mapped entities appear in text."""
        text_lower = text.lower()
        found = set()
        for entity in self.entity_capsule_map.keys():
            if entity.lower() in text_lower:
                found.add(entity)
        return found

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the woven memory."""
        return {
            "soft_memory_count": len(self.soft_memory_results),
            "capsule_count": len(self.related_capsules),
            "entities_matched": list(self.entity_capsule_map.keys()),
            "entities_unmatched": self.unmatched_entities,
            "has_woven_context": self.has_woven_context(),
        }


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

    def recall_with_context(
        self,
        message: str,
        orchestrator: 'MemoryOrchestrator',
        soft_memory_limit: int = 5,
        capsules_per_entity: int = 2,
    ) -> WovenMemory:
        """
        Recall past conversations and cross-reference with memory capsules.

        This is the core integration point between soft memory (past conversations)
        and hard memory (capsules). When a conversation mentions a person, this
        method surfaces both the conversation and the relational thread about them.

        Args:
            message: Current message to find context for
            orchestrator: Memory orchestrator for capsule queries
            soft_memory_limit: Maximum past conversations to return
            capsules_per_entity: Maximum capsules to fetch per entity

        Returns:
            WovenMemory combining soft and hard memory results

        Example:
            # User says "Remember when we talked about Sarah's project?"
            woven = soft_memory.recall_with_context(message, orchestrator)
            # Returns:
            # - Past conversations mentioning Sarah
            # - RelationalThread capsule about who Sarah is
        """
        # Step 1: Recall relevant past conversations
        soft_results = self.recall_relevant(message, limit=soft_memory_limit)

        # Step 2: Extract entities from soft memory results
        entities = self._extract_entities_from_results(soft_results)

        # Also extract entities from the current message
        message_entities = self._extract_entities_from_text(message)
        entities.update(message_entities)

        # Step 3: Query orchestrator for related capsules
        entity_capsule_map: dict[str, list['MemoryCapsule']] = {}
        all_capsules: list['MemoryCapsule'] = []
        unmatched_entities: list[str] = []

        for entity in entities:
            try:
                # Query for capsules matching this entity
                capsules = orchestrator.recall(
                    cue=entity.name,
                    limit=capsules_per_entity,
                    min_presence=0.2,  # Lower threshold for related context
                )

                # Filter for relational capsules (primary match for entities)
                # but also include other types that mention the entity
                matching_capsules = []
                for capsule in capsules:
                    # Check if this capsule is really about this entity
                    if self._capsule_matches_entity(capsule, entity.name):
                        matching_capsules.append(capsule)

                if matching_capsules:
                    entity_capsule_map[entity.name] = matching_capsules
                    all_capsules.extend(matching_capsules)
                else:
                    unmatched_entities.append(entity.name)

            except Exception as e:
                logger.debug(f"Failed to query capsules for entity {entity.name}: {e}")
                unmatched_entities.append(entity.name)

        # Deduplicate capsules
        seen_ids = set()
        unique_capsules = []
        for capsule in all_capsules:
            if capsule.id not in seen_ids:
                seen_ids.add(capsule.id)
                unique_capsules.append(capsule)

        return WovenMemory(
            soft_memory_results=soft_results,
            related_capsules=unique_capsules,
            entity_capsule_map=entity_capsule_map,
            unmatched_entities=unmatched_entities,
        )

    def _extract_entities_from_results(
        self,
        results: list[MessageSearchResult],
    ) -> set[EntityMatch]:
        """
        Extract potential entities from message search results.

        Looks for capitalized words and phrases that might be names
        or topics worth cross-referencing with capsules.
        """
        entities: set[EntityMatch] = set()

        for result in results:
            content = result.message.content
            extracted = self._extract_entities_from_text(content)
            entities.update(extracted)

        return entities

    def _extract_entities_from_text(self, text: str) -> set[EntityMatch]:
        """
        Extract potential entities from text.

        Uses multiple heuristics:
        1. Capitalized words (likely proper nouns)
        2. Quoted phrases
        3. Words following possessive patterns ("Sarah's", "John's")

        Args:
            text: Text to extract entities from

        Returns:
            Set of EntityMatch objects
        """
        entities: set[EntityMatch] = set()

        # Skip if text is too short
        if len(text) < 10:
            return entities

        # Pattern 1: Capitalized words that aren't at sentence start
        # Find capitalized words that appear mid-sentence
        cap_pattern = r'(?<=[a-z]\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        for match in re.finditer(cap_pattern, text):
            name = match.group(1)
            # Filter out common words that might be capitalized
            if name.lower() not in self._common_non_entities():
                entities.add(EntityMatch(
                    name=name,
                    source_text=text[max(0, match.start()-20):match.end()+20],
                    confidence=0.8,
                ))

        # Pattern 2: Possessive patterns like "Sarah's", "John's project"
        poss_pattern = r"([A-Z][a-z]+)'s\b"
        for match in re.finditer(poss_pattern, text):
            name = match.group(1)
            if name.lower() not in self._common_non_entities():
                entities.add(EntityMatch(
                    name=name,
                    source_text=text[max(0, match.start()-20):match.end()+20],
                    confidence=0.9,  # Higher confidence for possessive patterns
                ))

        # Pattern 3: Names at sentence start (less reliable)
        # "Sarah said..." or "John mentioned..."
        start_pattern = r'^([A-Z][a-z]+)\s+(?:said|mentioned|asked|told|thought|felt|wanted)'
        for match in re.finditer(start_pattern, text, re.MULTILINE):
            name = match.group(1)
            if name.lower() not in self._common_non_entities():
                entities.add(EntityMatch(
                    name=name,
                    source_text=text[match.start():match.end()+30],
                    confidence=0.7,
                ))

        # Pattern 4: "about [Name]" patterns
        about_pattern = r'about\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        for match in re.finditer(about_pattern, text, re.IGNORECASE):
            name = match.group(1)
            if name[0].isupper() and name.lower() not in self._common_non_entities():
                entities.add(EntityMatch(
                    name=name,
                    source_text=text[max(0, match.start()-10):match.end()+20],
                    confidence=0.85,
                ))

        return entities

    def _common_non_entities(self) -> set[str]:
        """Common words that might be capitalized but aren't entities."""
        return {
            # Days and months
            "monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday", "january", "february", "march",
            "april", "may", "june", "july", "august", "september",
            "october", "november", "december",
            # Common sentence starters
            "the", "this", "that", "these", "those", "here", "there",
            "what", "when", "where", "why", "how", "who", "which",
            "today", "tomorrow", "yesterday", "later", "earlier",
            # Pronouns sometimes capitalized
            "i", "you", "we", "they", "it",
            # Other common words
            "yes", "no", "maybe", "perhaps", "hello", "hi", "hey",
            "thanks", "thank", "please", "sorry", "okay", "ok",
        }

    def _capsule_matches_entity(
        self,
        capsule: 'MemoryCapsule',
        entity_name: str,
    ) -> bool:
        """
        Check if a capsule is actually about the given entity.

        Verifies that the capsule's content meaningfully relates to the entity,
        not just that it was returned by a cue phrase search.
        """
        entity_lower = entity_name.lower()

        # Check relational thread entity field
        if hasattr(capsule, 'entity'):
            if entity_lower in capsule.entity.lower():
                return True

        # Check cue phrases
        for cue in capsule.cue_phrases:
            if entity_lower in cue.lower():
                return True

        # Check content dictionary
        if capsule.content:
            content_str = str(capsule.content).lower()
            if entity_lower in content_str:
                return True

        return False

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
