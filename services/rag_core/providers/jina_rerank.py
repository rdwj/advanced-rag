"""Jina AI reranking provider.

Jina offers high-quality reranking models with competitive performance.

Usage:
    from rag_core.providers.jina_rerank import JinaRerankProvider

    provider = JinaRerankProvider(
        api_key="jina_...",
        model="jina-reranker-v2-base-multilingual",
    )
    result = provider.rerank(
        query="What is machine learning?",
        documents=["ML is AI", "Python code", "Neural networks"],
    )
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

import requests

from .base import RerankProvider, RerankResult

logger = logging.getLogger(__name__)


class JinaRerankProvider(RerankProvider):
    """Reranking provider for Jina AI API.

    Attributes:
        api_key: Jina API key.
        model: Model name for reranking.
        base_url: API endpoint URL.
    """

    DEFAULT_BASE_URL = "https://api.jina.ai"
    DEFAULT_MODEL = "jina-reranker-v2-base-multilingual"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: Optional[str] = None,
        max_documents: int = 1000,
    ):
        """Initialize the Jina reranking provider.

        Args:
            api_key: Jina API key.
            model: Model name to use.
            base_url: Optional custom API endpoint.
            max_documents: Maximum documents per rerank call.
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._max_documents = max_documents

    @property
    def default_model(self) -> str:
        return self._model

    @property
    def max_documents(self) -> int:
        return self._max_documents

    @property
    def supports_scores(self) -> bool:
        return True

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> RerankResult:
        """Rerank documents by relevance to query.

        Args:
            query: Query to rank against.
            documents: Documents to rerank.
            top_n: Maximum results to return. None means all.
            model: Optional model override.

        Returns:
            RerankResult with indices and scores.

        Raises:
            RuntimeError: If API call fails.
        """
        if not documents:
            return RerankResult(indices=[], scores=[], model=model or self._model)

        if not query:
            # No query - return passthrough order
            n = len(documents) if top_n is None else min(len(documents), top_n)
            return RerankResult(
                indices=list(range(n)),
                scores=[0.0] * n,
                model=model or self._model,
            )

        chosen_model = model or self._model

        url = f"{self._base_url}/v1/rerank"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": chosen_model,
            "query": query,
            "documents": list(documents),
        }

        if top_n is not None:
            payload["top_n"] = top_n

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            # Sort by relevance score descending
            sorted_results = sorted(
                results,
                key=lambda r: float(r.get("relevance_score", r.get("score", 0.0))),
                reverse=True,
            )

            indices = [int(r["index"]) for r in sorted_results]
            scores = [
                float(r.get("relevance_score", r.get("score", 0.0)))
                for r in sorted_results
            ]

            # Apply top_n limit
            if top_n is not None:
                indices = indices[:top_n]
                scores = scores[:top_n]

            return RerankResult(
                indices=indices,
                scores=scores,
                model=chosen_model,
            )

        except requests.RequestException as e:
            logger.error("Jina rerank API error: %s", e)
            raise RuntimeError(f"Jina rerank failed: {e}") from e
        except Exception as e:
            logger.error("Unexpected Jina rerank error: %s", e)
            raise RuntimeError(f"Jina rerank failed: {e}") from e

    def rerank_with_fallback(
        self,
        query: str,
        documents: Sequence[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> RerankResult:
        """Rerank with passthrough fallback on error.

        Same as rerank() but returns passthrough order instead of
        raising on failure.

        Args:
            query: Query to rank against.
            documents: Documents to rerank.
            top_n: Maximum results to return.
            model: Optional model override.

        Returns:
            RerankResult, using passthrough order if API fails.
        """
        try:
            return self.rerank(query, documents, top_n=top_n, model=model)
        except Exception as e:
            logger.warning("Jina rerank failed, using passthrough: %s", e)
            n = len(documents) if top_n is None else min(len(documents), top_n)
            return RerankResult(
                indices=list(range(n)),
                scores=None,
                model="passthrough",
            )


def create_provider(
    api_key: str,
    model: str = JinaRerankProvider.DEFAULT_MODEL,
    base_url: Optional[str] = None,
    **kwargs,
) -> JinaRerankProvider:
    """Factory function to create a Jina rerank provider.

    Args:
        api_key: Jina API key.
        model: Model name to use.
        base_url: Optional custom API endpoint.
        **kwargs: Additional arguments passed to provider.

    Returns:
        Configured JinaRerankProvider instance.
    """
    return JinaRerankProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        **kwargs,
    )
