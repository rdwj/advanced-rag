"""Configuration utilities for embedding service."""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI


def _build_client(api_key: str, base_url: Optional[str]) -> OpenAI:
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def get_embedding_model() -> str:
    return os.environ.get("EMBEDDING_MODEL", os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))


def get_embedding_client() -> OpenAI:
    api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("EMBEDDING_API_KEY or OPENAI_API_KEY must be set for embeddings")
    base_url: Optional[str] = os.environ.get("EMBEDDING_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    return _build_client(api_key, base_url)
