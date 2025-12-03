"""Token utilities for vector gateway."""
from __future__ import annotations


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text using tiktoken."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4
