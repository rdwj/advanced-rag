"""Configuration utilities for plan service."""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI


def _build_client(api_key: str, base_url: Optional[str]) -> OpenAI:
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def get_openai_plan_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_PLAN_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_PLAN_API_KEY or OPENAI_API_KEY must be set for planning")
    base_url: Optional[str] = os.environ.get("OPENAI_PLAN_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    return _build_client(api_key, base_url)


def get_plan_model() -> str:
    return os.environ.get("OPENAI_PLAN_MODEL", os.environ.get("PLAN_MODEL", "gpt-4.1-mini"))
