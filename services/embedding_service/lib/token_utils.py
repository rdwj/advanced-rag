"""Lightweight token estimation utilities.

We only need approximate counts to enforce prompt/context budgets before
calling an LLM. If `tiktoken` is available we use it; otherwise we fall back to
a simple heuristic of ~4 characters per token.
"""
from __future__ import annotations


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        # Heuristic: average 4 characters per token for English-ish text.
        return max(1, len(text) // 4)
