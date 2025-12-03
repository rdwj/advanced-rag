"""OpenAI-compatible embedding provider.

This provider works with:
- OpenAI API (default)
- Azure OpenAI
- vLLM embedding servers
- Text Embeddings Inference (TEI)
- Any OpenAI-compatible embedding API

Usage:
    from rag_core.providers.openai_compat import OpenAICompatEmbeddingProvider

    provider = OpenAICompatEmbeddingProvider(
        api_key="sk-...",
        model="text-embedding-3-small",
    )
    result = provider.embed(["Hello world"])
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

from openai import OpenAI

from .base import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class OpenAICompatEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for OpenAI and compatible APIs.

    Supports automatic batching and token limit handling.

    Attributes:
        client: OpenAI client instance.
        model: Model name for embeddings.
        _max_batch: Maximum texts per API call.
        _max_tokens: Maximum tokens per input.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        max_batch_size: int = 64,
        max_tokens_per_input: int = 8191,
        dimensions: Optional[int] = None,
    ):
        """Initialize the OpenAI-compatible embedding provider.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional custom API endpoint.
            max_batch_size: Maximum texts per API call.
            max_tokens_per_input: Maximum tokens per input text.
            dimensions: Optional output dimensions (for dimension reduction).
        """
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)

        self._model = model
        self._max_batch = max_batch_size
        self._max_tokens = max_tokens_per_input
        self._dimensions = dimensions

    @property
    def default_model(self) -> str:
        return self._model

    @property
    def max_batch_size(self) -> int:
        return self._max_batch

    @property
    def max_tokens_per_input(self) -> int:
        return self._max_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Estimate tokens in text using heuristic.

        Uses ~4 chars per token for quick estimation.
        For accurate counts, use rag_core.token_utils.estimate_tokens.
        """
        return max(1, len(text) // 4)

    def embed(
        self,
        texts: Sequence[str],
        model: Optional[str] = None,
        encoding_format: Optional[str] = None,
    ) -> EmbeddingResult:
        """Generate embeddings for texts.

        Args:
            texts: Texts to embed.
            model: Optional model override.
            encoding_format: Optional format ("float" or "base64").

        Returns:
            EmbeddingResult with embedding vectors.

        Raises:
            ValueError: If texts is empty.
            RuntimeError: If API call fails.
        """
        if not texts:
            return EmbeddingResult(vectors=[], model=model or self._model)

        chosen_model = model or self._model
        vectors: list[list[float]] = []
        total_usage = {"prompt_tokens": 0, "total_tokens": 0}

        # Batch by estimated token count
        batch: list[str] = []
        batch_tokens = 0
        max_batch_tokens = 3500  # Conservative batch limit

        for text in texts:
            # Handle None/empty
            text = text if text else ""

            # Estimate tokens
            est = self._estimate_tokens(text)

            # Truncate if exceeds per-input limit
            if est > self._max_tokens:
                keep_ratio = self._max_tokens / est
                text = text[: max(1, int(len(text) * keep_ratio))]
                est = self._estimate_tokens(text)

            # Flush batch if needed
            if batch and batch_tokens + est > max_batch_tokens:
                batch_vectors, usage = self._call_api(
                    batch, chosen_model, encoding_format
                )
                vectors.extend(batch_vectors)
                total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                total_usage["total_tokens"] += usage.get("total_tokens", 0)
                batch = []
                batch_tokens = 0

            batch.append(text)
            batch_tokens += est

        # Process remaining batch
        if batch:
            batch_vectors, usage = self._call_api(
                batch, chosen_model, encoding_format
            )
            vectors.extend(batch_vectors)
            total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_usage["total_tokens"] += usage.get("total_tokens", 0)

        return EmbeddingResult(
            vectors=vectors,
            model=chosen_model,
            usage=total_usage,
        )

    def _call_api(
        self,
        texts: list[str],
        model: str,
        encoding_format: Optional[str],
    ) -> tuple[list[list[float]], dict]:
        """Make API call and extract vectors.

        Args:
            texts: Batch of texts to embed.
            model: Model name.
            encoding_format: Optional encoding format.

        Returns:
            Tuple of (vectors, usage_dict).
        """
        kwargs: dict = {"model": model, "input": texts}

        if encoding_format:
            kwargs["encoding_format"] = encoding_format

        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions

        try:
            response = self.client.embeddings.create(**kwargs)
            vectors = [item.embedding for item in response.data]
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return vectors, usage
        except Exception as e:
            logger.error("OpenAI embedding API error: %s", e)
            raise RuntimeError(f"Embedding failed: {e}") from e


def create_provider(
    api_key: str,
    model: str = "text-embedding-3-small",
    base_url: Optional[str] = None,
    **kwargs,
) -> OpenAICompatEmbeddingProvider:
    """Factory function to create an OpenAI-compatible provider.

    Args:
        api_key: API key for authentication.
        model: Model name to use.
        base_url: Optional custom API endpoint.
        **kwargs: Additional arguments passed to provider.

    Returns:
        Configured OpenAICompatEmbeddingProvider instance.
    """
    return OpenAICompatEmbeddingProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        **kwargs,
    )
