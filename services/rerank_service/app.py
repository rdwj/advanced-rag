"""Rerank Service - FastAPI microservice for reranking search results."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, validator

# Import from rag_core shared library
from rag_core import rerank_documents, get_rerank_settings


AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rerank_service")
app = FastAPI(title="Rerank Service", version="0.1.0")


class RerankRequest(BaseModel):
    query: str
    documents: List[str] = Field(..., description="Documents to rerank")
    model: Optional[str] = None
    top_k: Optional[int] = Field(default=None, description="Optional cap on returned indices")

    @validator("documents")
    def _validate_documents(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("documents must be non-empty")
        return v


class RerankResponse(BaseModel):
    indices: List[int]
    model: Optional[str]
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
def healthz() -> dict[str, Any]:
    settings = get_rerank_settings()
    return {"status": "ok", "provider": settings.provider if settings else None, "model": settings.model if settings else None}


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest, _: None = Depends(_auth_dependency)) -> RerankResponse:
    start = time.time()
    try:
        # prefer_service=False to avoid circular calls (we ARE the service)
        indices = rerank_documents(
            request.query,
            request.documents,
            top_n=request.top_k,
            prefer_service=False,
            model=request.model,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = int((time.time() - start) * 1000)
    settings = get_rerank_settings()
    model = request.model or (settings.model if settings else None)
    logger.info("reranked docs=%d top_k=%s latency_ms=%d", len(request.documents), request.top_k, latency_ms)
    return RerankResponse(indices=indices, model=model, latency_ms=latency_ms)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8003")))
