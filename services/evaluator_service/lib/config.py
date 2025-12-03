"""Configuration utilities for evaluator service."""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI


def _build_client(api_key: str, base_url: Optional[str]) -> OpenAI:
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in the environment")
    base_url: Optional[str] = os.environ.get("OPENAI_BASE_URL")
    return _build_client(api_key, base_url)


def get_eval_model() -> str:
    return os.environ.get("OPENAI_EVAL_MODEL", "gpt-4.1-mini")
