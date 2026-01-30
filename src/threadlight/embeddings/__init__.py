"""
Embedding generation for semantic search in Threadlight.

Supports multiple embedding backends:
- Local models (sentence-transformers via transformers)
- OpenAI API (text-embedding-3-small)
- Configurable for other providers

Usage:
    from threadlight.embeddings import create_embedding_provider, LocalEmbeddings

    # Create provider
    provider = create_embedding_provider("local")

    # Generate embeddings
    embedding = provider.embed("Hello, world!")
    embeddings = provider.embed_batch(["Hello", "World"])
"""

from __future__ import annotations

import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Recommended embedding models (2025-2026)
RECOMMENDED_MODELS = {
    "embedding-gemma-300m": {
        "id": "google/embedding-gemma-300m",
        "dimensions": 768,
        "parameters": "308M",
        "size_mb": 250,
        "description": "Best-in-class <500M params, excellent for classification and clustering",
        "year": 2025,
    },
    "e5-small-v2": {
        "id": "intfloat/e5-small-v2",
        "dimensions": 384,
        "parameters": "33M",
        "size_mb": 100,
        "description": "Fast and efficient, modern replacement for MiniLM",
        "year": 2024,
    },
    "nomic-embed-v1.5": {
        "id": "nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768,
        "parameters": "137M",
        "size_mb": 400,
        "description": "Top long-context performance, fully open source",
        "year": 2025,
    },
    "bge-small-en-v1.5": {
        "id": "BAAI/bge-small-en-v1.5",
        "dimensions": 384,
        "parameters": "33M",
        "size_mb": 130,
        "description": "BAAI quality in small package",
        "year": 2024,
    },
    "e5-base-v2": {
        "id": "intfloat/e5-base-v2",
        "dimensions": 768,
        "parameters": "110M",
        "size_mb": 300,
        "description": "Balanced quality and speed",
        "year": 2024,
    },
    "all-MiniLM-L6-v2": {
        "id": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "parameters": "22M",
        "size_mb": 43,
        "description": "Legacy default (2020) - consider upgrading to a modern model",
        "year": 2020,
    },
}


def get_recommended_model(model_id: str) -> dict | None:
    """Get info about a recommended model."""
    return RECOMMENDED_MODELS.get(model_id)


def list_recommended_models() -> list[dict]:
    """List all recommended models sorted by quality."""
    return list(RECOMMENDED_MODELS.values())


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding implementations must provide these methods.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension for this provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    def health_check(self) -> bool:
        """Check if the provider is working."""
        try:
            result = self.embed("test")
            return len(result) == self.dimension
        except Exception as e:
            logger.warning(f"Embedding health check failed: {e}")
            return False


class LocalEmbeddings(EmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.

    Default model: intfloat/e5-small-v2 (fast, modern, 384 dimensions)

    Requires: pip install sentence-transformers
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-small-v2",
        device: Optional[str] = None,
        **kwargs: Any
    ):
        self._model_name = model_name
        self._model = None
        self._device = device
        self._dimension: Optional[int] = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

        logger.info(f"Loading embedding model: {self._model_name}")
        self._model = SentenceTransformer(self._model_name, device=self._device)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Dimension: {self._dimension}")

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load_model()
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]


class OpenAIEmbeddings(EmbeddingProvider):
    """
    OpenAI embedding provider using the embeddings API.

    Default model: text-embedding-3-small (1536 dimensions)

    Requires: OPENAI_API_KEY environment variable
    """

    # Dimensions for known models
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs: Any
    ):
        self._model_name = model_name
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._api_base = api_base or "https://api.openai.com/v1"

        if not self._api_key:
            raise ValueError(
                "OpenAI API key not provided. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

    @property
    def dimension(self) -> int:
        return self.MODEL_DIMENSIONS.get(self._model_name, 1536)

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        import httpx

        url = f"{self._api_base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model_name,
            "input": texts,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Sort by index to ensure order matches input
        results = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in results]


class NousEmbeddings(EmbeddingProvider):
    """
    Nous Research embedding provider (if they support embeddings).

    Falls back to local embeddings if not available.
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-small-v2",
        api_key: Optional[str] = None,
        api_base: str = "https://inference-api.nousresearch.com/v1",
        **kwargs: Any
    ):
        self._api_key = api_key or os.getenv("NOUS_API_KEY")
        self._api_base = api_base

        # For now, fall back to local embeddings
        # Nous Research may add embedding support in the future
        logger.info("Using local embeddings (Nous embedding API not yet available)")
        self._local = LocalEmbeddings(model_name=model_name, **kwargs)

    @property
    def dimension(self) -> int:
        return self._local.dimension

    @property
    def model_name(self) -> str:
        return self._local.model_name

    def embed(self, text: str) -> list[float]:
        return self._local.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._local.embed_batch(texts)


# Provider registry
_EMBEDDING_PROVIDERS: dict[str, type[EmbeddingProvider]] = {
    "local": LocalEmbeddings,
    "openai": OpenAIEmbeddings,
    "nous": NousEmbeddings,
}


def register_embedding_provider(name: str, provider_class: type[EmbeddingProvider]) -> None:
    """Register a custom embedding provider."""
    _EMBEDDING_PROVIDERS[name] = provider_class


def create_embedding_provider(
    provider_type: str = "local",
    **kwargs: Any
) -> EmbeddingProvider:
    """
    Create an embedding provider instance.

    Args:
        provider_type: Type of provider ("local", "openai", "nous")
        **kwargs: Provider-specific arguments

    Returns:
        EmbeddingProvider instance

    Example:
        provider = create_embedding_provider("local")
        provider = create_embedding_provider("openai", api_key="...")
    """
    if provider_type not in _EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider: {provider_type}. "
            f"Available: {list(_EMBEDDING_PROVIDERS.keys())}"
        )

    provider_class = _EMBEDDING_PROVIDERS[provider_type]
    return provider_class(**kwargs)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity score (-1 to 1)
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimensions must match: {len(a)} vs {len(b)}")

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


# Export public API
__all__ = [
    "EmbeddingProvider",
    "LocalEmbeddings",
    "OpenAIEmbeddings",
    "NousEmbeddings",
    "create_embedding_provider",
    "register_embedding_provider",
    "cosine_similarity",
    "RECOMMENDED_MODELS",
    "get_recommended_model",
    "list_recommended_models",
]
