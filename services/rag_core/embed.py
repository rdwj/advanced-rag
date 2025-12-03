"""Unified embedding implementation for RAG pipeline.

This module provides a single embed_texts function that:
1. Attempts to call the embedding service if EMBEDDING_SERVICE_URL is set
2. Falls back to direct provider calls if service unavailable
3. Handles batching and token limits automatically
4. Supports multiple provider types (OpenAI, Cohere, Caikit, etc.)

Usage:
    from rag_core.embed import embed_texts

    # Embed texts (will use service if configured, else direct API)
    vectors = embed_texts(["Hello world", "Goodbye world"])

    # Force direct API call (skip service)
    vectors = embed_texts(["Hello world"], prefer_service=False)

    # Specify model override
    vectors = embed_texts(["Hello world"], model="text-embedding-3-large")
"""
from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional

import requests

from .config import get_embedding_client, get_embedding_config, get_service_url
from .token_utils import estimate_tokens

logger = logging.getLogger(__name__)

# Lazy-loaded provider cache
_provider_cache: dict = {}


def _get_embedding_provider():
    """Get the configured embedding provider instance.

    Returns a cached provider instance based on the config type.
    Supports: openai-compatible, cohere, caikit
    """
    config = get_embedding_config()
    provider_type = config.type

    cache_key = f"{provider_type}:{config.base_url}:{config.model}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    if provider_type == "caikit":
        from .providers.caikit_embed import CaikitEmbeddingProvider
        provider = CaikitEmbeddingProvider.from_config(
            base_url=config.base_url,
            model=config.model,
            api_key_env=config.api_key_env,
            max_batch=config.max_batch,
        )
    elif provider_type == "cohere":
        from .providers.cohere_embed import CohereEmbeddingProvider
        provider = CohereEmbeddingProvider.from_config(
            base_url=config.base_url,
            model=config.model,
            api_key_env=config.api_key_env,
        )
    else:
        # Default to OpenAI-compatible (includes openai-compatible, openai)
        # Return None to use existing OpenAI client logic
        _provider_cache[cache_key] = None
        return None

    _provider_cache[cache_key] = provider
    return provider


def _embed_via_service(
    texts: List[str],
    model: Optional[str],
    encoding_format: Optional[str],
    timeout: int = 30,
) -> Optional[List[List[float]]]:
    """Attempt to embed texts via the embedding microservice.

    Args:
        texts: List of texts to embed.
        model: Optional model override.
        encoding_format: Optional encoding format (e.g., "float", "base64").
        timeout: Request timeout in seconds.

    Returns:
        List of embedding vectors if service call succeeds, None otherwise.
    """
    # Check for service URL from config or env
    service_url = get_service_url("embedding") or os.environ.get("EMBEDDING_SERVICE_URL")
    if not service_url:
        return None

    # Build request headers
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.environ.get("EMBEDDING_SERVICE_TOKEN") or os.environ.get("SERVICE_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Build payload
    payload: dict[str, object] = {"texts": texts}
    if model:
        payload["model"] = model
    if encoding_format:
        payload["encoding_format"] = encoding_format

    try:
        endpoint = service_url.rstrip("/") + "/embed"
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        vectors = data.get("vectors")
        if isinstance(vectors, list):
            return vectors
        logger.warning("Embedding service returned unexpected format: %s", type(data))
    except requests.RequestException as e:
        logger.warning("Embedding service call failed: %s", e)
    except Exception as e:
        logger.warning("Unexpected error calling embedding service: %s", e)

    return None


def _embed_batch_direct(
    texts: List[str],
    model: str,
    encoding_format: Optional[str],
    max_tokens_per_batch: int,
    max_input_tokens: int,
) -> List[List[float]]:
    """Embed texts directly using OpenAI API with batching.

    Args:
        texts: List of texts to embed.
        model: Model name to use.
        encoding_format: Optional encoding format.
        max_tokens_per_batch: Maximum total tokens per API call.
        max_input_tokens: Maximum tokens per individual input.

    Returns:
        List of embedding vectors.
    """
    client = get_embedding_client()
    vectors: List[List[float]] = []
    batch: List[str] = []
    current_tokens = 0

    for text in texts:
        est = estimate_tokens(text)

        # Truncate if single text exceeds limit
        if est > max_input_tokens:
            keep_ratio = max_input_tokens / est
            text = text[: max(1, int(len(text) * keep_ratio))]
            est = estimate_tokens(text)
            logger.debug("Truncated text from %d to %d tokens", est * 2, est)

        # Flush batch if adding this text would exceed limit
        if batch and current_tokens + est > max_tokens_per_batch:
            kwargs: dict[str, object] = {"model": model, "input": batch}
            if encoding_format:
                kwargs["encoding_format"] = encoding_format

            response = client.embeddings.create(**kwargs)
            vectors.extend([item.embedding for item in response.data])
            batch = []
            current_tokens = 0

        batch.append(text)
        current_tokens += est

    # Embed remaining batch
    if batch:
        kwargs = {"model": model, "input": batch}
        if encoding_format:
            kwargs["encoding_format"] = encoding_format

        response = client.embeddings.create(**kwargs)
        vectors.extend([item.embedding for item in response.data])

    return vectors


def embed_texts(
    texts: Iterable[str],
    model: Optional[str] = None,
    encoding_format: Optional[str] = None,
    prefer_service: bool = True,
    max_tokens_per_batch: Optional[int] = None,
    max_input_tokens: Optional[int] = None,
) -> List[List[float]]:
    """Generate embeddings for a list of texts.

    Uses the embedding microservice if available, otherwise falls back
    to direct OpenAI API calls with automatic batching.

    Args:
        texts: Iterable of texts to embed. None values are converted to "".
        model: Model name override. If not specified, uses config default.
        encoding_format: Optional encoding format (e.g., "float", "base64").
        prefer_service: If True, try embedding service first.
        max_tokens_per_batch: Max tokens per API batch (default: 3500).
        max_input_tokens: Max tokens per input text (default: 7500).

    Returns:
        List of embedding vectors, one per input text.
        Empty list if no texts provided.

    Example:
        >>> vectors = embed_texts(["Hello world", "Goodbye"])
        >>> len(vectors)
        2
        >>> len(vectors[0])  # Dimension depends on model
        1536
    """
    # Clean input texts
    clean_texts = [t if t is not None else "" for t in texts]
    if not clean_texts:
        return []

    # Try service first if preferred
    if prefer_service:
        via_service = _embed_via_service(clean_texts, model, encoding_format)
        if via_service is not None:
            return via_service

    # Get config for defaults
    config = get_embedding_config()
    chosen_model = model or config.model

    # Check if we should use a non-OpenAI provider
    provider = _get_embedding_provider()
    if provider is not None:
        # Use the configured provider (Caikit, Cohere, etc.)
        logger.debug("Using %s provider for embeddings", config.type)
        result = provider.embed(clean_texts)
        return result.vectors

    # Use config or parameter defaults for OpenAI-compatible
    batch_limit = max_tokens_per_batch or 3500
    input_limit = max_input_tokens or min(7500, config.max_tokens_per_input)

    return _embed_batch_direct(
        clean_texts,
        chosen_model,
        encoding_format,
        batch_limit,
        input_limit,
    )


def embed_query(
    query: str,
    model: Optional[str] = None,
    prefer_service: bool = True,
) -> List[float]:
    """Embed a single query string.

    Convenience wrapper around embed_texts for single queries.

    Args:
        query: Query text to embed.
        model: Optional model override.
        prefer_service: If True, try embedding service first.

    Returns:
        Embedding vector for the query.
    """
    vectors = embed_texts([query], model=model, prefer_service=prefer_service)
    return vectors[0] if vectors else []
