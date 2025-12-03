"""Evaluator Service - FastAPI microservice for evaluating RAG answer quality."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, validator

from lib.evaluate import evaluate_answer
from lib.config import get_eval_model


AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator_service")
app = FastAPI(title="Evaluator Service", version="0.1.0")


class EvalRequest(BaseModel):
    question: str
    answer: str
    plan: Dict[str, Any] = Field(default_factory=dict)
    keywords: List[str] = Field(default_factory=list)

    @validator("keywords", pre=True)
    def _normalize_keywords(cls, v):
        if v is None:
            return []
        return list(v)


class EvalResponse(BaseModel):
    score: float
    feedback: str
    suggested_plan: Optional[Dict[str, Any]]
    model: str
    latency_ms: int
    raw: Optional[str] = Field(default=None, description="Raw evaluator JSON from the model")


def _auth_dependency(authorization: str = Header(None), x_api_key: str = Header(None)) -> None:
    if not AUTH_TOKEN:
        return
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "model": get_eval_model()}


@app.post("/evaluate", response_model=EvalResponse)
def evaluate(request: EvalRequest, _: None = Depends(_auth_dependency)) -> EvalResponse:
    start = time.time()
    try:
        result = evaluate_answer(
            question=request.question,
            answer=request.answer,
            plan=request.plan,
            keywords=request.keywords,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = int((time.time() - start) * 1000)
    logger.info("evaluated latency_ms=%d score=%.3f", latency_ms, float(result.get("score", 0.0)))
    return EvalResponse(
        score=float(result.get("score", 0.0)),
        feedback=str(result.get("feedback", "")),
        suggested_plan=result.get("suggested_plan"),
        model=str(result.get("model", get_eval_model())),
        latency_ms=latency_ms,
        raw=result.get("_raw_eval"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8004")))
