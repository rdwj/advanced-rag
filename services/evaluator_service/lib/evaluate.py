"""Core evaluation functionality for evaluator service."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .config import get_openai_client, get_eval_model


def evaluate_answer(
    question: str, answer: str, plan: Dict[str, Any], keywords: List[str]
) -> Dict[str, Any]:
    """Score an answer for groundedness/completeness and suggest plan tweaks."""

    keyword_hint = ", ".join(keywords) if keywords else "none specified"
    prompt = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"""You are grading a RAG answer. Score groundedness and completeness from 0 to 1.
- Every sentence must include a citation like [s1]; missing citations or unverifiable claims should pull the score below 0.5.
- If the question requests a timeframe/interval (e.g., screening cadence), the answer must state that interval with a citation or score <= 0.6.
- Key terms to verify in cited spans: {keyword_hint}
- Keep feedback short (one or two sentences).
- suggested_plan should tweak only window_size, overlap, or mode and be null if the current plan seems fine.
Return ONLY valid JSON (no prose) with keys:
{{
  "score": <number between 0 and 1 for groundedness/completeness>,
  "feedback": "<short string>",
  "suggested_plan": {{
    "window_size": <int>,
    "overlap": <int>,
    "mode": "<tokens|lines|chars>"
  }} | null
}}

Question: {question}
Answer: {answer}
Current plan: {json.dumps(plan)}
""",
            }
        ],
    }

    client = get_openai_client()
    model = get_eval_model()

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [prompt],
        "response_format": {"type": "json_object"},
    }
    try:
        kwargs["temperature"] = 0.0
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("temperature", None)
        resp = client.chat.completions.create(**kwargs)

    raw = resp.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"score": 0.0, "feedback": "Could not parse evaluator output", "suggested_plan": None}
    parsed["_raw_eval"] = raw
    parsed["model"] = model
    return parsed
