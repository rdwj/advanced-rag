"""Caikit reranking provider.

This provider implements the Caikit NLP reranking API used by IBM/Red Hat
model serving platforms with cross-encoder reranking models.

API Endpoint: POST /api/v1/task/rerank

Request format:
    {
        "inputs": {
            "query": "search query",
            "documents": [{"text": "doc1"}, {"text": "doc2"}]
        },
        "model_id": "model-name",
        "parameters": {"top_n": 10}  # optional
    }

Response format:
    {
        "result": {
            "query": "search query",
            "scores": [
                {"index": 0, "score": 8.13, "text": "doc1", "document": {...}},
                {"index": 2, "score": -4.11, "text": "doc2", "document": {...}}
            ]
        },
        "producer_id": {...},
        "input_token_count": int
    }

Note: Scores are already sorted by relevance (highest first).
The index field contains the original position in the input documents list.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Sequence, Tuple

import httpx

from .base import RerankProvider, RerankResult

logger = logging.getLogger(__name__)


class CaikitRerankProvider(RerankProvider):
    """Caikit NLP reranking provider.

    Implements reranking using the Caikit NLP REST API with cross-encoder
    models, commonly deployed on Red Hat OpenShift AI / IBM watsonx platforms.

    Attributes:
        base_url: Caikit service base URL
        model: Model ID as registered in Caikit (e.g., "ms-marco-reranker")
        api_key: Optional API key for authenticated endpoints
        timeout: Request timeout in seconds
        max_documents: Maximum documents per rerank request
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_documents: int = 100,
    ):
        """Initialize the Caikit rerank provider.

        Args:
            base_url: Base URL of the Caikit service
            model: Model ID to use for reranking
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_documents: Maximum documents per rerank request
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._max_documents = max_documents

    @property
    def default_model(self) -> str:
        """Default model name for this provider."""
        return self.model

    @property
    def max_documents(self) -> int:
        """Maximum documents per rerank call."""
        return self._max_documents

    def _get_headers(self) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> RerankResult:
        """Rerank documents by relevance to the query.

        Args:
            query: The search query
            documents: List of document texts to rerank
            top_n: Maximum number of results to return (default: all)
            model: Optional model override (ignored, uses instance model)

        Returns:
            RerankResult with indices and scores sorted by relevance

        Raises:
            httpx.HTTPStatusError: If the API request fails
            ValueError: If the response format is unexpected
        """
        docs_list = list(documents)
        if not docs_list:
            return RerankResult(indices=[], scores=[], model=self.model)

        if top_n is None:
            top_n = len(docs_list)

        # Caikit expects documents as list of dicts with "text" key
        doc_objects = [{"text": doc} for doc in docs_list]

        # Limit to max_documents
        if len(doc_objects) > self.max_documents:
            logger.warning(
                f"Truncating {len(doc_objects)} documents to {self.max_documents}"
            )
            doc_objects = doc_objects[: self.max_documents]

        url = f"{self.base_url}/api/v1/task/rerank"
        payload = {
            "inputs": {
                "query": query,
                "documents": doc_objects,
            },
            "model_id": self.model,
            "parameters": {"top_n": top_n},
        }

        with httpx.Client(timeout=self.timeout, verify=False) as client:
            response = client.post(url, json=payload, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        # Extract scores from response
        # Format: {"result": {"scores": [{"index": 0, "score": 8.13, ...}]}}
        scores_list = data.get("result", {}).get("scores", [])

        # Scores are already sorted by relevance (highest first)
        indices = []
        scores = []
        for item in scores_list[:top_n]:
            indices.append(item["index"])
            scores.append(item["score"])

        return RerankResult(indices=indices, scores=scores, model=self.model)

    def rerank_with_scores(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None,
    ) -> List[Tuple[int, float]]:
        """Rerank and return list of (index, score) tuples.

        This is a convenience method that returns the same data as rerank()
        but in a different format.

        Args:
            query: The search query
            documents: List of document texts
            top_n: Maximum number of results

        Returns:
            List of (original_index, relevance_score) tuples
        """
        result = self.rerank(query, documents, top_n)
        return list(zip(result.indices, result.scores))

    @classmethod
    def from_config(
        cls,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key_env: Optional[str] = None,
        max_documents: int = 100,
        **kwargs,
    ) -> "CaikitRerankProvider":
        """Create provider from configuration.

        Args:
            base_url: Caikit service URL
            model: Model ID
            api_key_env: Environment variable name containing API key
            max_documents: Maximum documents per request
            **kwargs: Additional arguments (ignored)

        Returns:
            Configured CaikitRerankProvider instance
        """
        if not base_url:
            raise ValueError("base_url is required for Caikit rerank provider")
        if not model:
            raise ValueError("model is required for Caikit rerank provider")

        api_key = None
        if api_key_env:
            api_key = os.environ.get(api_key_env)

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            max_documents=max_documents,
        )
