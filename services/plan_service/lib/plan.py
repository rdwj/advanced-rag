"""Core planning functionality for plan service."""
from __future__ import annotations

import json
from typing import Any, Dict

from .config import get_openai_plan_client, get_plan_model


def build_chunking_prompt(text: str, metadata: Dict[str, Any]) -> str:
    """Build a prompt for asking an LLM to design a chunking plan.

    The response is expected to be a JSON object containing the
    ChunkingPlan fields. Validation of the result should be handled by
    the caller.
    """

    max_chars = 15000
    sample = text[:max_chars]

    return f"""
You are designing a chunking strategy for retrieval-augmented generation (RAG).

Document metadata:
{json.dumps(metadata, indent=2)}

Document sample (may be truncated):
\"\"\"{sample}\"\"\"

Return ONLY a JSON object with these fields:

- window_size: integer > 0
- overlap: integer >= 0 and < window_size
- mode: one of ["chars", "tokens", "lines"]
- break_on_headings: boolean
- max_chunks: integer or null
- notes: short string

Example:
{{
  "window_size": 200,
  "overlap": 40,
  "mode": "tokens",
  "break_on_headings": true,
  "max_chunks": null,
  "notes": "Use headings to avoid splitting sections."
}}
"""


def ask_llm_for_plan(text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Call an LLM to obtain a ChunkingPlan as a JSON object."""

    prompt = build_chunking_prompt(text, metadata)

    client = get_openai_plan_client()
    model = get_plan_model()

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )

    content = response.choices[0].message.content.strip()
    plan: Dict[str, Any] = json.loads(content)
    return plan
