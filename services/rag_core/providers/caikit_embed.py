"""Caikit embedding provider.

This provider implements the Caikit NLP embedding API used by IBM/Red Hat
model serving platforms. It supports both single and batch embedding requests.

API Endpoints:
- Single: POST /api/v1/task/embedding
- Batch: POST /api/v1/task/embedding-tasks

Request format:
    {
        "inputs": "text" | ["text1", "text2"],
        "model_id": "model-name"
    }

Response format (single):
    {
        "result": {"data": {"values": [float, ...]}},
        "producer_id": {...},
        "input_token_count": int
    }

Response format (batch):
    {
        "results": {"vectors": [{"data": {"values": [float, ...]}}]},
        "producer_id": {...},
        "input_token_count": int
    }
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Sequence

import httpx

from .base import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class CaikitEmbeddingProvider(EmbeddingProvider):
    """Caikit NLP embedding provider.

    Implements embedding generation using the Caikit NLP REST API,
    commonly deployed on Red Hat OpenShift AI / IBM watsonx platforms.

    Attributes:
        base_url: Caikit service base URL (e.g., https://model-service.apps.cluster.com)
        model: Model ID as registered in Caikit (e.g., "granite-embedding-278m")
        api_key: Optional API key for authenticated endpoints
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_batch: int = 64,
    ):
        """Initialize the Caikit embedding provider.

        Args:
            base_url: Base URL of the Caikit service
            model: Model ID to use for embeddings
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_batch: Maximum texts per batch request
        """
        # Normalize base URL
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._max_batch = max_batch

    @property
    def default_model(self) -> str:
        """Default model name for this provider."""
        return self.model

    @property
    def max_batch_size(self) -> int:
        """Maximum texts per API call."""
        return self._max_batch

    def _get_headers(self) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def embed(
        self,
        texts: Sequence[str],
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Uses batch endpoint for multiple texts, single endpoint for one text.

        Args:
            texts: List of text strings to embed
            model: Optional model override (ignored, uses instance model)

        Returns:
            EmbeddingResult with vectors for each input text

        Raises:
            httpx.HTTPStatusError: If the API request fails
            ValueError: If the response format is unexpected
        """
        texts_list = list(texts)
        if not texts_list:
            return EmbeddingResult(vectors=[], model=self.model)

        all_embeddings: List[List[float]] = []

        # Process in batches
        for i in range(0, len(texts_list), self._max_batch):
            batch = texts_list[i : i + self._max_batch]
            batch_embeddings = self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return EmbeddingResult(vectors=all_embeddings, model=self.model)

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts.

        Args:
            texts: Batch of texts (should be <= max_batch)

        Returns:
            List of embedding vectors
        """
        if len(texts) == 1:
            # Use single embedding endpoint
            return [self._embed_single(texts[0])]

        # Use batch endpoint
        url = f"{self.base_url}/api/v1/task/embedding-tasks"
        payload = {
            "inputs": texts,
            "model_id": self.model,
        }

        with httpx.Client(timeout=self.timeout, verify=False) as client:
            response = client.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        # Extract embeddings from response
        # Format: {"results": {"vectors": [{"data": {"values": [...]}}]}}
        vectors = data.get("results", {}).get("vectors", [])
        if len(vectors) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(vectors)}"
            )

        embeddings = []
        for vec in vectors:
            values = vec.get("data", {}).get("values", [])
            if not values:
                raise ValueError("Empty embedding returned from Caikit API")
            embeddings.append(values)

        return embeddings

    def _embed_single(self, text: str) -> List[float]:
        """Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/api/v1/task/embedding"
        payload = {
            "inputs": text,
            "model_id": self.model,
        }

        with httpx.Client(timeout=self.timeout, verify=False) as client:
            response = client.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        # Extract embedding from response
        # Format: {"result": {"data": {"values": [...]}}}
        values = data.get("result", {}).get("data", {}).get("values", [])
        if not values:
            raise ValueError("Empty embedding returned from Caikit API")

        return values

    @classmethod
    def from_config(
        cls,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key_env: Optional[str] = None,
        max_batch: int = 64,
        **kwargs,
    ) -> "CaikitEmbeddingProvider":
        """Create provider from configuration.

        Args:
            base_url: Caikit service URL
            model: Model ID
            api_key_env: Environment variable name containing API key
            max_batch: Maximum texts per batch
            **kwargs: Additional arguments (ignored)

        Returns:
            Configured CaikitEmbeddingProvider instance
        """
        if not base_url:
            raise ValueError("base_url is required for Caikit provider")
        if not model:
            raise ValueError("model is required for Caikit provider")

        api_key = None
        if api_key_env:
            api_key = os.environ.get(api_key_env)

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_batch=max_batch,
        )
