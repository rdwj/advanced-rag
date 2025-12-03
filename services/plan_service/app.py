"""Plan Service - FastAPI microservice for generating chunking plans."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from lib.plan import ask_llm_for_plan
from lib.config import get_plan_model


AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plan_service")
app = FastAPI(title="Plan Service", version="0.1.0")


class PlanRequest(BaseModel):
    text: str = Field(..., description="Document sample or full text")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Metadata describing the document")
    profile: Optional[str] = Field(
        default=None, description="Optional profile name for future routing (unused for now)"
    )


class PlanResponse(BaseModel):
    plan: Dict[str, Any]
    model: str
    latency_ms: int


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
def healthz() -> Dict[str, Any]:
    return {"status": "ok", "model": get_plan_model()}


@app.post("/plan", response_model=PlanResponse)
def generate_plan(request: PlanRequest, _: None = Depends(_auth_dependency)) -> PlanResponse:
    start = time.time()
    try:
        plan = ask_llm_for_plan(request.text, request.meta)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = int((time.time() - start) * 1000)
    model = get_plan_model()
    logger.info("generated plan model=%s latency_ms=%d", model, latency_ms)
    return PlanResponse(plan=plan, model=model, latency_ms=latency_ms)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
