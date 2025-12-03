"""Core embedding functionality for vector gateway."""
from __future__ import annotations

import os
from typing import Iterable, List, Optional

import requests

from .config import get_embedding_client, get_embedding_model
from .token_utils import estimate_tokens


def _embed_via_service(
    texts: List[str], model: Optional[str], encoding_format: Optional[str], timeout: int = 30
) -> Optional[List[List[float]]]:
    service_url = os.environ.get("EMBEDDING_SERVICE_URL")
    if not service_url:
        return None

    headers = {"Accept": "application/json"}
    token = os.environ.get("EMBEDDING_SERVICE_TOKEN") or os.environ.get("SERVICE_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"texts": texts}
    if model:
        payload["model"] = model
    if encoding_format:
        payload["encoding_format"] = encoding_format

    try:
        resp = requests.post(service_url.rstrip("/") + "/embed", json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        vectors = data.get("vectors")
        if isinstance(vectors, list):
            return vectors
    except Exception:
        return None
    return None


def embed_texts(
    texts: Iterable[str],
    model: Optional[str] = None,
    encoding_format: Optional[str] = None,
    prefer_service: bool = True,
) -> List[List[float]]:
    """Generate embeddings for a list of texts using OpenAI API or external service."""
    clean_texts = [t if t is not None else "" for t in texts]
    if not clean_texts:
        return []

    if prefer_service:
        via_service = _embed_via_service(clean_texts, model, encoding_format)
        if via_service is not None:
            return via_service

    client = get_embedding_client()
    chosen_model = model or get_embedding_model()

    max_tokens_per_batch = 3500
    max_input_tokens = 7500
    vectors: List[List[float]] = []
    batch: List[str] = []
    current_tokens = 0

    for text in clean_texts:
        est = estimate_tokens(text)
        if est > max_input_tokens:
            # Truncate proportionally to stay under the per-input limit.
            keep_ratio = max_input_tokens / est
            text = text[: max(1, int(len(text) * keep_ratio))]
            est = estimate_tokens(text)
        if batch and current_tokens + est > max_tokens_per_batch:
            response = client.embeddings.create(
                model=chosen_model, input=batch, **({"encoding_format": encoding_format} if encoding_format else {})
            )
            vectors.extend([item.embedding for item in response.data])
            batch = []
            current_tokens = 0
        batch.append(text)
        current_tokens += est

    if batch:
        response = client.embeddings.create(
            model=chosen_model, input=batch, **({"encoding_format": encoding_format} if encoding_format else {})
        )
        vectors.extend([item.embedding for item in response.data])

    return vectors
