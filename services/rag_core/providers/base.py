"""Base interfaces for embedding and reranking providers.

This module defines abstract base classes that provider implementations
should follow. These interfaces enable consistent usage across different
provider backends (OpenAI, Cohere, Jina, etc.).

Usage:
    from rag_core.providers.base import EmbeddingProvider, RerankProvider

    class MyCustomEmbedder(EmbeddingProvider):
        def embed(self, texts: list[str]) -> list[list[float]]:
            # Custom implementation
            ...
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class EmbeddingResult:
    """Result from an embedding operation.

    Attributes:
        vectors: List of embedding vectors.
        model: Model name used for embedding.
        usage: Optional token usage information.
    """
    vectors: List[List[float]]
    model: str
    usage: Optional[dict] = None


@dataclass
class RerankResult:
    """Result from a reranking operation.

    Attributes:
        indices: Document indices in descending relevance order.
        scores: Relevance scores corresponding to indices (if available).
        model: Model name used for reranking.
    """
    indices: List[int]
    scores: Optional[List[float]] = None
    model: Optional[str] = None


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Implementations should handle:
    - API authentication
    - Batching of requests
    - Error handling with appropriate fallbacks
    """

    @abstractmethod
    def embed(
        self,
        texts: Sequence[str],
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: Texts to embed.
            model: Optional model override.

        Returns:
            EmbeddingResult with vectors for each input text.

        Raises:
            ValueError: If texts is empty or contains invalid input.
            RuntimeError: If embedding fails after retries.
        """
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model name for this provider."""
        ...

    @property
    def max_batch_size(self) -> int:
        """Maximum texts per API call. Override in subclass."""
        return 64

    @property
    def max_tokens_per_input(self) -> int:
        """Maximum tokens per input text. Override in subclass."""
        return 8191


class RerankProvider(ABC):
    """Abstract base class for reranking providers.

    Implementations should handle:
    - API authentication
    - Document limit enforcement
    - Error handling with passthrough fallback
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> RerankResult:
        """Rerank documents by relevance to a query.

        Args:
            query: Query to rank against.
            documents: Documents to rerank.
            top_n: Maximum results to return. None means all.
            model: Optional model override.

        Returns:
            RerankResult with indices in descending relevance order.

        Raises:
            ValueError: If query or documents are invalid.
            RuntimeError: If reranking fails and passthrough is disabled.
        """
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model name for this provider."""
        ...

    @property
    def max_documents(self) -> int:
        """Maximum documents per rerank call. Override in subclass."""
        return 1000

    @property
    def supports_scores(self) -> bool:
        """Whether this provider returns relevance scores."""
        return True


class PassthroughRerankProvider(RerankProvider):
    """No-op reranker that preserves document order.

    Used when reranking is disabled or as a fallback when
    the configured provider fails.
    """

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> RerankResult:
        """Return documents in original order.

        Args:
            query: Ignored.
            documents: Documents to return indices for.
            top_n: Optional limit on indices returned.
            model: Ignored.

        Returns:
            RerankResult with indices in original order.
        """
        n = len(documents)
        if top_n is not None:
            n = min(n, top_n)
        return RerankResult(
            indices=list(range(n)),
            scores=None,
            model="passthrough",
        )

    @property
    def default_model(self) -> str:
        return "passthrough"

    @property
    def supports_scores(self) -> bool:
        return False
