"""Cohere embedding provider.

Cohere has a different API shape than OpenAI, requiring a dedicated
provider implementation.

Usage:
    from rag_core.providers.cohere_embed import CohereEmbeddingProvider

    provider = CohereEmbeddingProvider(
        api_key="co-...",
        model="embed-english-v3.0",
    )
    result = provider.embed(["Hello world"])
"""
from __future__ import annotations

import logging
from typing import Literal, Optional, Sequence

import requests

from .base import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)

# Cohere input types
InputType = Literal["search_document", "search_query", "classification", "clustering"]


class CohereEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for Cohere API.

    Cohere embeddings have input_type parameter that affects embedding
    for different use cases (document storage vs query).

    Attributes:
        api_key: Cohere API key.
        model: Model name for embeddings.
        base_url: API endpoint URL.
    """

    DEFAULT_BASE_URL = "https://api.cohere.com"
    DEFAULT_MODEL = "embed-english-v3.0"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: Optional[str] = None,
        max_batch_size: int = 96,
        max_tokens_per_input: int = 512,
        truncate: bool = True,
    ):
        """Initialize the Cohere embedding provider.

        Args:
            api_key: Cohere API key.
            model: Model name to use.
            base_url: Optional custom API endpoint.
            max_batch_size: Maximum texts per API call.
            max_tokens_per_input: Maximum tokens per input text.
            truncate: Whether to auto-truncate long inputs.
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._max_batch = max_batch_size
        self._max_tokens = max_tokens_per_input
        self._truncate = truncate

    @property
    def default_model(self) -> str:
        return self._model

    @property
    def max_batch_size(self) -> int:
        return self._max_batch

    @property
    def max_tokens_per_input(self) -> int:
        return self._max_tokens

    def embed(
        self,
        texts: Sequence[str],
        model: Optional[str] = None,
        input_type: InputType = "search_document",
    ) -> EmbeddingResult:
        """Generate embeddings for texts.

        Args:
            texts: Texts to embed.
            model: Optional model override.
            input_type: Cohere input type. Use "search_document" for
                documents being stored, "search_query" for queries.

        Returns:
            EmbeddingResult with embedding vectors.

        Raises:
            ValueError: If texts is empty.
            RuntimeError: If API call fails.
        """
        if not texts:
            return EmbeddingResult(vectors=[], model=model or self._model)

        chosen_model = model or self._model
        all_vectors: list[list[float]] = []
        total_tokens = 0

        # Process in batches
        text_list = list(texts)
        for i in range(0, len(text_list), self._max_batch):
            batch = text_list[i : i + self._max_batch]
            vectors, tokens = self._call_api(batch, chosen_model, input_type)
            all_vectors.extend(vectors)
            total_tokens += tokens

        return EmbeddingResult(
            vectors=all_vectors,
            model=chosen_model,
            usage={"total_tokens": total_tokens},
        )

    def _call_api(
        self,
        texts: list[str],
        model: str,
        input_type: InputType,
    ) -> tuple[list[list[float]], int]:
        """Make Cohere API call.

        Args:
            texts: Batch of texts to embed.
            model: Model name.
            input_type: Cohere input type.

        Returns:
            Tuple of (vectors, token_count).
        """
        url = f"{self._base_url}/v1/embed"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"],
        }

        if self._truncate:
            payload["truncate"] = "END"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            # Cohere returns embeddings in different formats based on embedding_types
            embeddings = data.get("embeddings", {})

            # Handle new format with embedding_types
            if isinstance(embeddings, dict):
                vectors = embeddings.get("float", [])
            else:
                # Legacy format - direct list
                vectors = embeddings

            # Get token usage
            meta = data.get("meta", {})
            billed_units = meta.get("billed_units", {})
            tokens = billed_units.get("input_tokens", 0)

            return vectors, tokens

        except requests.RequestException as e:
            logger.error("Cohere embedding API error: %s", e)
            raise RuntimeError(f"Cohere embedding failed: {e}") from e
        except Exception as e:
            logger.error("Unexpected Cohere error: %s", e)
            raise RuntimeError(f"Cohere embedding failed: {e}") from e

    def embed_query(self, query: str, model: Optional[str] = None) -> list[float]:
        """Embed a single query for search.

        Uses input_type="search_query" for optimal query embedding.

        Args:
            query: Query text to embed.
            model: Optional model override.

        Returns:
            Embedding vector for the query.
        """
        result = self.embed([query], model=model, input_type="search_query")
        return result.vectors[0] if result.vectors else []

    def embed_documents(
        self,
        documents: Sequence[str],
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """Embed documents for storage.

        Uses input_type="search_document" for optimal document embedding.

        Args:
            documents: Documents to embed.
            model: Optional model override.

        Returns:
            List of embedding vectors.
        """
        result = self.embed(documents, model=model, input_type="search_document")
        return result.vectors


def create_provider(
    api_key: str,
    model: str = CohereEmbeddingProvider.DEFAULT_MODEL,
    base_url: Optional[str] = None,
    **kwargs,
) -> CohereEmbeddingProvider:
    """Factory function to create a Cohere provider.

    Args:
        api_key: Cohere API key.
        model: Model name to use.
        base_url: Optional custom API endpoint.
        **kwargs: Additional arguments passed to provider.

    Returns:
        Configured CohereEmbeddingProvider instance.
    """
    return CohereEmbeddingProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        **kwargs,
    )
