"""
Storage backends for Threadlight memory capsules.

Supports multiple backends:
- SQLite (default): Simple, portable, no setup required
- In-memory: For testing and ephemeral use
- YAML/JSON: Human-readable archives (future)

Each backend implements the StorageBackend interface, providing:
- Full CRUD operations for capsules
- Proposal management for consent-based memory creation
- Batch operations for decay processing
- Query filtering by type, tags, recency, and presence score
"""

from threadlight.storage.base import StorageBackend, CapsuleFilter, MemoryProposal
from threadlight.storage.sqlite import SQLiteStorage
from threadlight.storage.memory import InMemoryStorage

__all__ = [
    # Abstract interface
    "StorageBackend",
    # Data classes
    "CapsuleFilter",
    "MemoryProposal",
    # Implementations
    "SQLiteStorage",
    "InMemoryStorage",
    # Factory
    "create_storage",
]


def create_storage(backend: str, **kwargs) -> StorageBackend:
    """
    Factory function to create a storage backend.

    Args:
        backend: The backend type ("sqlite" or "memory")
        **kwargs: Backend-specific configuration
            - For SQLite: path (str) - database file path
            - For memory: no additional options

    Returns:
        An initialized StorageBackend instance

    Raises:
        ValueError: If backend type is not recognized

    Example:
        # Create SQLite storage
        storage = create_storage("sqlite", path="./memories.db")
        storage.initialize()

        # Create in-memory storage for testing
        storage = create_storage("memory")
        storage.initialize()
    """
    backends = {
        "sqlite": SQLiteStorage,
        "memory": InMemoryStorage,
    }

    if backend not in backends:
        raise ValueError(
            f"Unknown storage backend: {backend}. "
            f"Available: {list(backends.keys())}"
        )

    return backends[backend](**kwargs)
