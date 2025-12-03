"""Configuration utilities for rerank service."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


def _build_client(api_key: str, base_url: Optional[str]) -> OpenAI:
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


@dataclass
class RerankSettings:
    provider: str
    model: str
    api_key: Optional[str]
    base_url: Optional[str]


def get_rerank_settings() -> Optional[RerankSettings]:
    provider = os.environ.get("RERANK_PROVIDER", "none").lower()
    if provider in {"", "none"}:
        return None

    # For cohere, try COHERE_API_KEY first
    if provider == "cohere":
        api_key = os.environ.get("COHERE_API_KEY") or os.environ.get("RERANK_API_KEY")
    else:
        api_key = os.environ.get("RERANK_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("RERANK_API_KEY (or COHERE_API_KEY for cohere) must be set for reranking")

    base_url: Optional[str] = os.environ.get("RERANK_BASE_URL")
    if provider == "openai" and not base_url:
        base_url = os.environ.get("OPENAI_BASE_URL")

    default_model = "rerank-english-v3.0" if provider == "cohere" else "gpt-4.1-mini"
    model = os.environ.get("RERANK_MODEL", os.environ.get("OPENAI_RERANK_MODEL", default_model))

    return RerankSettings(provider=provider, model=model, api_key=api_key, base_url=base_url)


def get_rerank_client() -> Optional[OpenAI]:
    settings = get_rerank_settings()
    if not settings or settings.provider != "openai":
        return None
    return _build_client(settings.api_key or "", settings.base_url)
