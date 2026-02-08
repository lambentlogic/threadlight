"""
Embedding manager for Threadlight.

Coordinates embedding generation and semantic search across
memories and conversations.

Usage:
    manager = EmbeddingManager(provider, storage)

    # Generate embeddings for a capsule
    manager.generate_embeddings_for_capsule(capsule)

    # Batch generate for all memories without embeddings
    stats = manager.batch_generate_embeddings()

    # Semantic search
    results = manager.search_memories("things about creativity", limit=5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Callable

from threadlight.capsules.base import MemoryCapsule, CapsuleType
from threadlight.storage.base import StorageBackend, Message, MessageSearchResult, CapsuleFilter
from threadlight.embeddings import EmbeddingProvider, cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class SemanticSearchResult:
    """Result from semantic search."""

    item: MemoryCapsule | Message
    similarity_score: float
    item_type: str  # "capsule" or "message"

    # For messages, include conversation context
    conversation_name: Optional[str] = None
    conversation_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        if self.item_type == "capsule":
            return {
                "type": "capsule",
                "capsule_id": self.item.id,
                "capsule_type": self.item.type.value,
                "similarity_score": self.similarity_score,
                "content": self.item.to_dict(),
            }
        else:
            return {
                "type": "message",
                "message_id": self.item.id,
                "conversation_id": self.conversation_id,
                "conversation_name": self.conversation_name,
                "similarity_score": self.similarity_score,
                "role": self.item.role,
                "content": self.item.content,
                "timestamp": self.item.timestamp.isoformat() if self.item.timestamp else None,
            }


@dataclass
class EmbeddingStats:
    """Statistics from embedding generation."""

    capsules_processed: int = 0
    capsules_updated: int = 0
    messages_processed: int = 0
    messages_updated: int = 0
    errors: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsules_processed": self.capsules_processed,
            "capsules_updated": self.capsules_updated,
            "messages_processed": self.messages_processed,
            "messages_updated": self.messages_updated,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


class EmbeddingManager:
    """
    Manages embedding generation and semantic search.

    Coordinates between embedding providers and storage backends
    to enable semantic/meaning-based search over memories and
    conversations.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        storage: StorageBackend,
        batch_size: int = 100,
        auto_generate: bool = True,
    ):
        """
        Initialize the embedding manager.

        Args:
            provider: Embedding provider to use
            storage: Storage backend for persistence
            batch_size: Batch size for bulk operations
            auto_generate: Whether to auto-generate embeddings on save
        """
        self.provider = provider
        self.storage = storage
        self.batch_size = batch_size
        self.auto_generate = auto_generate

    def _get_capsule_text(self, capsule: MemoryCapsule) -> str:
        """Extract searchable text from a capsule."""
        parts = []

        # Add cue phrases
        if capsule.cue_phrases:
            parts.extend(capsule.cue_phrases)

        # Type-specific content extraction
        content = capsule.content

        if capsule.type == CapsuleType.RELATIONAL:
            if "entity" in content:
                parts.append(content["entity"])
            if "summary" in content:
                parts.append(content["summary"])
            if "quality" in content:
                parts.append(content["quality"])
            elif "tone" in content:
                parts.append(content["tone"])

        elif capsule.type == CapsuleType.MYTH_SEED:
            if "seed" in content:
                parts.append(content["seed"])
            if "origin" in content:
                parts.append(content["origin"])
            if "function" in content:
                parts.append(content["function"])

        elif capsule.type == CapsuleType.RITUAL:
            if "name" in content:
                parts.append(content["name"])
            if "description" in content:
                parts.append(content["description"])
            if "response_style" in content:
                parts.append(content["response_style"])

        elif capsule.type == CapsuleType.WITNESS:
            if "moment" in content:
                parts.append(content["moment"])
            if "feeling" in content:
                parts.append(content["feeling"])

        elif capsule.type == CapsuleType.STYLE:
            if "tone_base" in content:
                parts.append(content["tone_base"])
            if "permissions" in content:
                parts.extend(content["permissions"])
            if "constraints" in content:
                parts.extend(content["constraints"])

        else:
            # Custom type - extract all string values
            if "text" in content:
                parts.append(content["text"])
            for key, value in content.items():
                if isinstance(value, str) and key != "capsule_subtype":
                    parts.append(value)

        return " ".join(str(p) for p in parts if p)

    def generate_embedding_for_capsule(
        self,
        capsule: MemoryCapsule,
        save: bool = True,
    ) -> Optional[list[float]]:
        """
        Generate embedding for a single capsule.

        Args:
            capsule: The memory capsule
            save: Whether to save the embedding to storage

        Returns:
            The embedding vector, or None on failure
        """
        try:
            text = self._get_capsule_text(capsule)
            if not text:
                logger.debug(f"No text content for capsule {capsule.id}")
                return None

            embedding = self.provider.embed(text)
            capsule.embedding = embedding

            if save:
                self.storage.update_capsule(capsule)

            logger.debug(f"Generated embedding for capsule {capsule.id}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for capsule {capsule.id}: {e}")
            return None

    def generate_embedding_for_message(
        self,
        message: Message,
        save: bool = True,
    ) -> Optional[list[float]]:
        """
        Generate embedding for a single message.

        Args:
            message: The message
            save: Whether to save the embedding to storage

        Returns:
            The embedding vector, or None on failure
        """
        try:
            if not message.content:
                return None

            embedding = self.provider.embed(message.content)
            message.embedding = embedding

            if save:
                self.storage.save_message(message)

            logger.debug(f"Generated embedding for message {message.id}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for message {message.id}: {e}")
            return None

    def batch_generate_embeddings(
        self,
        include_capsules: bool = True,
        include_messages: bool = True,
        progress_callback: Optional[Callable[[EmbeddingStats], None]] = None,
    ) -> EmbeddingStats:
        """
        Generate embeddings for all items that don't have them.

        Args:
            include_capsules: Process memory capsules
            include_messages: Process conversation messages
            progress_callback: Optional callback for progress updates

        Returns:
            Statistics about the operation
        """
        import time
        start_time = time.time()
        stats = EmbeddingStats()

        # Process capsules
        if include_capsules:
            capsules = self.get_capsules_needing_embeddings()
            stats.capsules_processed = len(capsules)

            for i in range(0, len(capsules), self.batch_size):
                batch = capsules[i:i + self.batch_size]
                texts = [self._get_capsule_text(c) for c in batch]

                # Filter out empty texts
                valid_pairs = [(c, t) for c, t in zip(batch, texts) if t]

                if valid_pairs:
                    try:
                        embeddings = self.provider.embed_batch([t for _, t in valid_pairs])

                        for (capsule, _), embedding in zip(valid_pairs, embeddings):
                            capsule.embedding = embedding
                            self.storage.update_capsule(capsule)
                            stats.capsules_updated += 1

                    except Exception as e:
                        logger.error(f"Batch embedding failed: {e}")
                        stats.errors += 1

                if progress_callback:
                    stats.duration_seconds = time.time() - start_time
                    progress_callback(stats)

        # Process messages
        if include_messages:
            messages = self.get_messages_needing_embeddings()
            stats.messages_processed = len(messages)

            for i in range(0, len(messages), self.batch_size):
                batch = messages[i:i + self.batch_size]
                texts = [m.content for m in batch if m.content]

                # Filter out empty content
                valid_pairs = [(m, t) for m, t in zip(batch, texts) if t]

                if valid_pairs:
                    try:
                        embeddings = self.provider.embed_batch([t for _, t in valid_pairs])

                        for (message, _), embedding in zip(valid_pairs, embeddings):
                            message.embedding = embedding
                            self.storage.save_message(message)
                            stats.messages_updated += 1

                    except Exception as e:
                        logger.error(f"Batch message embedding failed: {e}")
                        stats.errors += 1

                if progress_callback:
                    stats.duration_seconds = time.time() - start_time
                    progress_callback(stats)

        stats.duration_seconds = time.time() - start_time
        logger.info(
            f"Embedding generation complete: "
            f"{stats.capsules_updated}/{stats.capsules_processed} capsules, "
            f"{stats.messages_updated}/{stats.messages_processed} messages, "
            f"{stats.errors} errors, {stats.duration_seconds:.1f}s"
        )

        return stats

    def get_capsules_needing_embeddings(self) -> list[MemoryCapsule]:
        """Get all capsules that don't have embeddings."""
        # Use the optimized storage method if available
        if hasattr(self.storage, 'get_capsules_needing_embeddings'):
            return self.storage.get_capsules_needing_embeddings(limit=10000)
        # Fallback: get all capsules and filter in Python
        # Explicitly bypass profile scoping to get ALL capsules
        all_capsules = self.storage.list_capsules(CapsuleFilter(
            limit=10000,
            profile_scope=None,  # Explicit: no profile filtering
            include_shared=True,  # Explicit: include everything
        ))
        return [c for c in all_capsules if c.embedding is None]

    def get_messages_needing_embeddings(self, limit: int = 10000) -> list[Message]:
        """Get all messages that don't have embeddings."""
        # This requires a custom query - we'll implement it in storage
        if hasattr(self.storage, 'get_messages_without_embeddings'):
            return self.storage.get_messages_without_embeddings(limit=limit)
        else:
            # Fallback: get recent conversations and check messages
            messages = []
            conversations = self.storage.list_conversations(limit=100)
            for conv in conversations:
                conv_messages = self.storage.get_messages(conv.id, limit=1000)
                messages.extend(m for m in conv_messages if m.embedding is None)
                if len(messages) >= limit:
                    break
            return messages[:limit]

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        threshold: float = 0.5,
        types: Optional[list[CapsuleType]] = None,
    ) -> list[SemanticSearchResult]:
        """
        Search memories semantically by meaning.

        Args:
            query: Search query text
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)
            types: Optional list of capsule types to filter

        Returns:
            List of search results sorted by similarity
        """
        # Generate query embedding
        query_embedding = self.provider.embed(query)

        # Get capsules with embeddings - search across all profiles
        capsules = self.storage.list_capsules(CapsuleFilter(
            limit=10000,
            profile_scope=None,  # Search across all profiles
            include_shared=True,
        ))
        capsules_with_embeddings = [c for c in capsules if c.embedding is not None]

        # Filter by type if specified
        if types:
            capsules_with_embeddings = [c for c in capsules_with_embeddings if c.type in types]

        # Calculate similarities
        results = []
        for capsule in capsules_with_embeddings:
            similarity = cosine_similarity(query_embedding, capsule.embedding)
            if similarity >= threshold:
                results.append(SemanticSearchResult(
                    item=capsule,
                    similarity_score=similarity,
                    item_type="capsule",
                ))

        # Sort by similarity and limit
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:limit]

    def search_conversations(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[SemanticSearchResult]:
        """
        Search conversation messages semantically.

        Args:
            query: Search query text
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of search results sorted by similarity
        """
        # Generate query embedding
        query_embedding = self.provider.embed(query)

        # Use storage's semantic search if available
        if hasattr(self.storage, 'search_messages_by_embedding'):
            raw_results = self.storage.search_messages_by_embedding(
                query_embedding,
                limit=limit,
                threshold=threshold,
            )
            return [
                SemanticSearchResult(
                    item=r.message,
                    similarity_score=r.relevance_score,
                    item_type="message",
                    conversation_name=r.conversation_name,
                    conversation_id=r.message.conversation_id,
                )
                for r in raw_results
            ]

        # Fallback: load messages and compute similarities in memory
        results = []
        conversations = self.storage.list_conversations(limit=100)

        for conv in conversations:
            messages = self.storage.get_messages(conv.id, limit=500)
            for message in messages:
                if message.embedding is not None:
                    similarity = cosine_similarity(query_embedding, message.embedding)
                    if similarity >= threshold:
                        results.append(SemanticSearchResult(
                            item=message,
                            similarity_score=similarity,
                            item_type="message",
                            conversation_name=conv.name,
                            conversation_id=conv.id,
                        ))

        # Sort by similarity and limit
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:limit]

    def search_all(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
        include_memories: bool = True,
        include_conversations: bool = True,
    ) -> list[SemanticSearchResult]:
        """
        Search both memories and conversations semantically.

        Args:
            query: Search query text
            limit: Maximum total results
            threshold: Minimum similarity score
            include_memories: Include memory capsules
            include_conversations: Include conversation messages

        Returns:
            Combined results sorted by similarity
        """
        results = []

        if include_memories:
            results.extend(self.search_memories(query, limit=limit, threshold=threshold))

        if include_conversations:
            results.extend(self.search_conversations(query, limit=limit, threshold=threshold))

        # Sort combined results and limit
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:limit]

    def clear_all_embeddings(self) -> dict[str, int]:
        """
        Clear all embeddings from memories and messages.

        This is useful when switching embedding models, as embeddings from
        different models are incompatible (different dimensions/semantic spaces).

        Returns:
            Dictionary with counts: {"capsules_cleared": N, "messages_cleared": M}
        """
        capsules_cleared = 0
        messages_cleared = 0

        # Clear capsule embeddings - across all profiles
        all_capsules = self.storage.list_capsules(CapsuleFilter(
            limit=10000,
            profile_scope=None,  # Clear across all profiles
            include_shared=True,
        ))
        for capsule in all_capsules:
            if capsule.embedding is not None:
                capsule.embedding = None
                self.storage.update_capsule(capsule)
                capsules_cleared += 1

        # Clear message embeddings
        if hasattr(self.storage, 'clear_all_message_embeddings'):
            # Use optimized storage method if available
            messages_cleared = self.storage.clear_all_message_embeddings()
        else:
            # Fallback: iterate through conversations
            conversations = self.storage.list_conversations(limit=1000)
            for conv in conversations:
                messages = self.storage.get_messages(conv.id, limit=10000)
                for message in messages:
                    if message.embedding is not None:
                        message.embedding = None
                        self.storage.save_message(message)
                        messages_cleared += 1

        logger.info(
            f"Cleared embeddings: {capsules_cleared} capsules, {messages_cleared} messages"
        )

        return {
            "capsules_cleared": capsules_cleared,
            "messages_cleared": messages_cleared,
        }

    def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about embedding coverage."""
        # Use count_capsules for total count (more efficient for stats)
        # When filter is None, count_capsules returns ALL capsules regardless of scope
        total_capsules = self.storage.count_capsules()

        # For counting embeddings, we need to check each capsule
        # Use a high limit to get all capsules, explicitly no profile filtering
        all_capsules = self.storage.list_capsules(CapsuleFilter(
            limit=10000,
            profile_scope=None,  # Explicit: no profile filtering
            include_shared=True,  # Explicit: include everything
        ))
        capsules_with_embeddings = sum(1 for c in all_capsules if c.embedding is not None)

        # Use actual total from count_capsules (handles case where limit is exceeded)
        if total_capsules > len(all_capsules):
            # If there are more capsules than our limit, we can't accurately count embeddings
            # Use the count we have as a lower bound
            logger.warning(f"Capsule count ({total_capsules}) exceeds limit, embedding count may be incomplete")

        # Count messages with embeddings
        total_messages = self.storage.count_messages()
        messages_with_embeddings = 0
        if hasattr(self.storage, 'count_messages_with_embeddings'):
            messages_with_embeddings = self.storage.count_messages_with_embeddings()

        return {
            "provider": self.provider.model_name,
            "dimension": self.provider.dimension,
            "capsules": {
                "total": total_capsules,
                "with_embeddings": capsules_with_embeddings,
                "coverage": capsules_with_embeddings / total_capsules if total_capsules else 0,
            },
            "messages": {
                "total": total_messages,
                "with_embeddings": messages_with_embeddings,
                "coverage": messages_with_embeddings / total_messages if total_messages else 0,
            },
        }


def create_embedding_manager(
    provider_type: str = "local",
    storage: StorageBackend = None,
    **kwargs: Any
) -> EmbeddingManager:
    """
    Create an embedding manager with the specified provider.

    Args:
        provider_type: Type of embedding provider
        storage: Storage backend
        **kwargs: Provider-specific arguments

    Returns:
        Configured EmbeddingManager
    """
    from threadlight.embeddings import create_embedding_provider

    provider = create_embedding_provider(provider_type, **kwargs)
    return EmbeddingManager(
        provider=provider,
        storage=storage,
        batch_size=kwargs.get("batch_size", 100),
        auto_generate=kwargs.get("auto_generate", True),
    )
