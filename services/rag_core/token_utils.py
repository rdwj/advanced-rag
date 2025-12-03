"""Lightweight token estimation utilities.

We only need approximate counts to enforce prompt/context budgets before
calling an LLM. If `tiktoken` is available we use it; otherwise we fall back to
a simple heuristic of ~4 characters per token.

Usage:
    from rag_core.token_utils import estimate_tokens, exceeds_context

    # Estimate tokens in text
    tokens = estimate_tokens("Hello world")

    # Check if text exceeds context limit
    if exceeds_context(long_text, context_limit=8192):
        print("Text is too long!")
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=4)
def _get_encoding(encoding_name: str):
    """Get tiktoken encoding, cached for performance.

    Args:
        encoding_name: Name of the encoding (e.g., "cl100k_base").

    Returns:
        tiktoken encoding object, or None if tiktoken unavailable.
    """
    try:
        import tiktoken  # type: ignore
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        return None


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text string.

    Uses tiktoken if available for accurate counts, otherwise falls back
    to a heuristic of ~4 characters per token.

    Args:
        text: Text to estimate tokens for.
        encoding_name: Tiktoken encoding name. Default is "cl100k_base"
            which is used by GPT-4, GPT-3.5-turbo, and text-embedding models.

    Returns:
        Estimated number of tokens. Always at least 1.

    Example:
        >>> estimate_tokens("Hello world")
        2
        >>> estimate_tokens("")
        1
    """
    if not text:
        return 1

    enc = _get_encoding(encoding_name)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass

    # Heuristic fallback: average 4 characters per token for English-ish text.
    return max(1, len(text) // 4)


def exceeds_context(
    text: str,
    context_limit: int,
    buffer: int = 2048,
    encoding_name: str = "cl100k_base",
) -> bool:
    """Check if text exceeds a context window limit.

    Useful for determining if text needs to be truncated before
    sending to an LLM.

    Args:
        text: Text to check.
        context_limit: Maximum context window size in tokens.
        buffer: Safety buffer to reserve for prompts/responses.
            Default 2048 tokens.
        encoding_name: Tiktoken encoding name for token estimation.

    Returns:
        True if text tokens exceed (context_limit - buffer).

    Example:
        >>> exceeds_context("Short text", context_limit=8192)
        False
        >>> exceeds_context("..." * 10000, context_limit=4096)
        True
    """
    tokens = estimate_tokens(text, encoding_name=encoding_name)
    return tokens > max(0, context_limit - buffer)


def truncate_to_tokens(
    text: str,
    max_tokens: int,
    encoding_name: str = "cl100k_base",
) -> str:
    """Truncate text to fit within a token limit.

    Uses tiktoken if available for accurate truncation, otherwise
    falls back to character-based approximation.

    Args:
        text: Text to truncate.
        max_tokens: Maximum allowed tokens.
        encoding_name: Tiktoken encoding name.

    Returns:
        Truncated text that fits within max_tokens.
    """
    if not text or max_tokens <= 0:
        return ""

    enc = _get_encoding(encoding_name)
    if enc is not None:
        try:
            tokens = enc.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return enc.decode(tokens[:max_tokens])
        except Exception:
            pass

    # Heuristic fallback: assume 4 chars per token
    estimated = estimate_tokens(text, encoding_name)
    if estimated <= max_tokens:
        return text

    keep_ratio = max_tokens / estimated
    return text[: max(1, int(len(text) * keep_ratio))]


def count_tokens_in_messages(
    messages: list[dict],
    encoding_name: str = "cl100k_base",
) -> int:
    """Estimate tokens in a list of chat messages.

    Accounts for message structure overhead (role, content markers).

    Args:
        messages: List of message dicts with "role" and "content" keys.
        encoding_name: Tiktoken encoding name.

    Returns:
        Estimated total tokens including message overhead.
    """
    total = 0
    for msg in messages:
        # Each message has ~4 tokens overhead for role markers
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content, encoding_name)
        elif isinstance(content, list):
            # Handle multi-part content (e.g., vision models)
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"], encoding_name)

    # Add priming tokens
    total += 3

    return total
