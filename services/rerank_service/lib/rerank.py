"""Core reranking functionality for rerank service."""
from __future__ import annotations

from typing import List, Sequence

import requests

from .config import get_rerank_settings


def rerank_documents(
    query: str, docs: Sequence[str], top_k: int | None = None
) -> List[int]:
    """Return document indices in the new order. Falls back to pass-through on errors."""

    settings = get_rerank_settings()
    if not settings:
        return list(range(len(docs) if top_k is None else min(len(docs), top_k)))

    if settings.provider == "cohere":
        url = (settings.base_url or "https://api.cohere.com") + "/v1/rerank"
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.model,
            "query": query,
            "documents": list(docs),
        }
        if top_k is not None:
            payload["top_n"] = top_k
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            # results items have {index, relevance_score}
            order = sorted(results, key=lambda r: float(r.get("relevance_score", 0.0)), reverse=True)
            indices = [int(r["index"]) for r in order]
            if top_k is not None:
                indices = indices[:top_k]
            return indices
        except Exception:
            return list(range(len(docs) if top_k is None else min(len(docs), top_k)))

    # Unknown provider: pass-through.
    return list(range(len(docs) if top_k is None else min(len(docs), top_k)))
