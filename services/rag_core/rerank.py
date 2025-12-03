"""Unified reranking implementation for RAG pipeline.

This module provides a single rerank_documents function that:
1. Attempts to call the rerank service if RERANK_SERVICE_URL is set
2. Falls back to direct provider calls if service unavailable
3. Implements Cohere reranking API
4. Provides passthrough mode when reranking is disabled

Usage:
    from rag_core.rerank import rerank_documents

    # Rerank documents (returns indices in new order)
    query = "What is machine learning?"
    docs = ["ML is a subset of AI", "Python is a language", "Neural networks learn"]
    indices = rerank_documents(query, docs, top_n=2)
    # indices might be [0, 2] meaning docs[0] and docs[2] are most relevant

    # Force direct API call (skip service)
    indices = rerank_documents(query, docs, prefer_service=False)
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Sequence

import requests

from .config import get_rerank_settings, get_service_url

logger = logging.getLogger(__name__)


def _passthrough_order(docs: Sequence[str], top_n: Optional[int]) -> List[int]:
    """Return passthrough order (original indices).

    Args:
        docs: Document sequence.
        top_n: Optional limit on returned indices.

    Returns:
        List of indices in original order, truncated if top_n specified.
    """
    n = len(docs)
    if top_n is not None:
        n = min(n, top_n)
    return list(range(n))


def _call_rerank_service(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int] = None,
    model: Optional[str] = None,
    timeout: int = 30,
) -> Optional[List[int]]:
    """Attempt to rerank via the rerank microservice.

    Args:
        query: Query to rank against.
        docs: Documents to rerank.
        top_n: Optional limit on returned indices.
        model: Optional model override.
        timeout: Request timeout in seconds.

    Returns:
        List of document indices in relevance order, or None if service unavailable.
    """
    # Check for service URL from config or env
    service_url = get_service_url("rerank") or os.environ.get("RERANK_SERVICE_URL")
    if not service_url:
        return None

    # Build request headers
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.environ.get("RERANK_SERVICE_TOKEN") or os.environ.get("SERVICE_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Build payload
    payload: dict[str, object] = {
        "query": query,
        "documents": list(docs),
    }
    if top_n is not None:
        payload["top_k"] = int(top_n)
    if model:
        payload["model"] = model

    try:
        endpoint = service_url.rstrip("/") + "/rerank"
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Service returns {"indices": [0, 2, 1, ...]}
        indices = data.get("indices") if isinstance(data, dict) else None
        if isinstance(indices, list):
            return [int(i) for i in indices]
        logger.warning("Rerank service returned unexpected format: %s", type(data))
    except requests.RequestException as e:
        logger.warning("Rerank service call failed: %s", e)
    except Exception as e:
        logger.warning("Unexpected error calling rerank service: %s", e)

    return None


def _rerank_cohere(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int],
    model: str,
    api_key: str,
    base_url: Optional[str],
    timeout: int = 30,
) -> List[int]:
    """Rerank using Cohere API.

    Args:
        query: Query to rank against.
        docs: Documents to rerank.
        top_n: Optional limit on returned documents.
        model: Cohere model name.
        api_key: Cohere API key.
        base_url: Optional custom base URL.
        timeout: Request timeout in seconds.

    Returns:
        List of document indices in relevance order.
    """
    url = (base_url or "https://api.cohere.com") + "/v1/rerank"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, object] = {
        "model": model,
        "query": query,
        "documents": list(docs),
    }
    if top_n is not None:
        payload["top_n"] = top_n

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Cohere returns {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
        results = data.get("results", [])

        # Sort by relevance score descending
        order = sorted(
            results,
            key=lambda r: float(r.get("relevance_score", 0.0)),
            reverse=True,
        )

        indices = [int(r["index"]) for r in order]

        # Respect top_n limit
        if top_n is not None:
            indices = indices[:top_n]

        return indices

    except requests.RequestException as e:
        logger.warning("Cohere rerank failed: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)
    except Exception as e:
        logger.warning("Unexpected Cohere error: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)


def _rerank_caikit(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int],
    model: str,
    base_url: str,
    api_key: Optional[str] = None,
    timeout: int = 60,
) -> List[int]:
    """Rerank using Caikit NLP API.

    Args:
        query: Query to rank against.
        docs: Documents to rerank.
        top_n: Optional limit on returned documents.
        model: Caikit model ID.
        base_url: Caikit service base URL.
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds.

    Returns:
        List of document indices in relevance order.
    """
    url = base_url.rstrip("/") + "/api/v1/task/rerank"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Caikit expects documents as list of dicts with "text" key
    doc_objects = [{"text": doc} for doc in docs]

    payload: dict[str, object] = {
        "inputs": {
            "query": query,
            "documents": doc_objects,
        },
        "model_id": model,
    }
    if top_n is not None:
        payload["parameters"] = {"top_n": top_n}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout, verify=False)
        resp.raise_for_status()
        data = resp.json()

        # Caikit returns {"result": {"scores": [{"index": 0, "score": 8.13, ...}]}}
        # Already sorted by relevance (highest first)
        scores = data.get("result", {}).get("scores", [])

        indices = [int(r["index"]) for r in scores]

        if top_n is not None:
            indices = indices[:top_n]

        return indices

    except requests.RequestException as e:
        logger.warning("Caikit rerank failed: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)
    except Exception as e:
        logger.warning("Unexpected Caikit error: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)


def _rerank_jina(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int],
    model: str,
    api_key: str,
    base_url: Optional[str],
    timeout: int = 30,
) -> List[int]:
    """Rerank using Jina AI API.

    Args:
        query: Query to rank against.
        docs: Documents to rerank.
        top_n: Optional limit on returned documents.
        model: Jina model name.
        api_key: Jina API key.
        base_url: Optional custom base URL.
        timeout: Request timeout in seconds.

    Returns:
        List of document indices in relevance order.
    """
    url = (base_url or "https://api.jina.ai") + "/v1/rerank"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict[str, object] = {
        "model": model,
        "query": query,
        "documents": list(docs),
    }
    if top_n is not None:
        payload["top_n"] = top_n

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Jina returns similar format to Cohere
        results = data.get("results", [])

        order = sorted(
            results,
            key=lambda r: float(r.get("relevance_score", r.get("score", 0.0))),
            reverse=True,
        )

        indices = [int(r["index"]) for r in order]

        if top_n is not None:
            indices = indices[:top_n]

        return indices

    except requests.RequestException as e:
        logger.warning("Jina rerank failed: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)
    except Exception as e:
        logger.warning("Unexpected Jina error: %s, using passthrough", e)
        return _passthrough_order(docs, top_n)


def rerank_documents(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int] = None,
    prefer_service: bool = True,
    model: Optional[str] = None,
) -> List[int]:
    """Rerank documents by relevance to a query.

    Uses the rerank microservice if available, otherwise falls back
    to direct provider API calls. Returns passthrough order if
    reranking is disabled or fails.

    Args:
        query: Query to rank documents against.
        docs: Sequence of document texts to rerank.
        top_n: Optional maximum number of indices to return.
            If None, returns all documents in ranked order.
        prefer_service: If True, try rerank service first.
        model: Optional model override.

    Returns:
        List of document indices in descending relevance order.
        Example: [2, 0, 1] means docs[2] is most relevant, then docs[0], docs[1].

    Example:
        >>> query = "What is deep learning?"
        >>> docs = ["Python basics", "Neural network training", "Deep learning intro"]
        >>> indices = rerank_documents(query, docs, top_n=2)
        >>> indices
        [2, 1]  # docs[2] and docs[1] are most relevant
    """
    if not docs:
        return []

    # Try service first if preferred
    if prefer_service:
        via_service = _call_rerank_service(query, docs, top_n=top_n, model=model)
        if via_service is not None:
            return via_service

    # Get rerank settings
    settings = get_rerank_settings()
    if not settings:
        return _passthrough_order(docs, top_n)

    provider = settings.provider.lower()

    # Passthrough provider
    if provider in {"passthrough", "none", ""}:
        return _passthrough_order(docs, top_n)

    # Cohere provider
    if provider == "cohere":
        if not settings.api_key:
            logger.warning("Cohere API key not set, using passthrough")
            return _passthrough_order(docs, top_n)
        return _rerank_cohere(
            query,
            docs,
            top_n,
            model or settings.model,
            settings.api_key,
            settings.base_url,
        )

    # Jina provider
    if provider == "jina":
        if not settings.api_key:
            logger.warning("Jina API key not set, using passthrough")
            return _passthrough_order(docs, top_n)
        return _rerank_jina(
            query,
            docs,
            top_n,
            model or settings.model,
            settings.api_key,
            settings.base_url,
        )

    # Caikit provider
    if provider == "caikit":
        if not settings.base_url:
            logger.warning("Caikit base_url not set, using passthrough")
            return _passthrough_order(docs, top_n)
        return _rerank_caikit(
            query,
            docs,
            top_n,
            model or settings.model,
            settings.base_url,
            settings.api_key,  # Optional for Caikit
        )

    # Unknown provider - log warning and passthrough
    logger.warning("Unknown rerank provider: %s, using passthrough", provider)
    return _passthrough_order(docs, top_n)


def rerank_with_scores(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int] = None,
    model: Optional[str] = None,
) -> List[tuple[int, float]]:
    """Rerank documents and return scores.

    Similar to rerank_documents but also returns relevance scores
    when available from the provider.

    Args:
        query: Query to rank documents against.
        docs: Sequence of document texts to rerank.
        top_n: Optional maximum number of results.
        model: Optional model override.

    Returns:
        List of (index, score) tuples in descending relevance order.
        Score is 0.0 if not available from provider.

    Note:
        Currently only direct Cohere calls return actual scores.
        Service calls and passthrough return index with 0.0 score.
    """
    # For now, delegate to rerank_documents and add dummy scores
    # Future enhancement: implement full score support
    indices = rerank_documents(query, docs, top_n=top_n, model=model)
    return [(idx, 0.0) for idx in indices]


def get_rerank_config_for_backward_compat():
    """Get client and model settings for reranking (legacy).

    This function provides backward compatibility with existing code
    that expects {"client": OpenAI, "model": str} dict.

    Returns:
        Dict with client and model, or None if reranking disabled.
    """
    from .config import get_rerank_client

    settings = get_rerank_settings()
    if not settings:
        return None
    client = get_rerank_client()
    return {"client": client, "model": settings.model}


# Alias for backward compatibility
def rerank_pass_through(
    query: str,
    docs: Sequence[str],
    top_n: Optional[int] = None,
) -> List[str]:
    """Placeholder reranker that preserves order (legacy).

    Returns document texts rather than indices for backward compatibility.

    Args:
        query: Ignored.
        docs: Documents to return.
        top_n: Optional limit.

    Returns:
        List of document texts in original order.
    """
    if top_n is None:
        return list(docs)
    return list(docs[:top_n])
