"""Core embedding functionality for embedding service."""
from __future__ import annotations

from typing import Iterable, List, Optional

from .config import get_embedding_client, get_embedding_model
from .token_utils import estimate_tokens


def embed_texts(
    texts: Iterable[str],
    model: Optional[str] = None,
    encoding_format: Optional[str] = None,
) -> List[List[float]]:
    """Generate embeddings for a list of texts using OpenAI API."""
    clean_texts = [t if t is not None else "" for t in texts]
    if not clean_texts:
        return []

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
