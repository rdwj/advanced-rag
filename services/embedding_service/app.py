"""Embedding Service - FastAPI microservice for generating text embeddings."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, validator

# Import from rag_core shared library
from rag_core import embed_texts, get_embedding_model


AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
MAX_BATCH = int(os.environ.get("EMBEDDING_MAX_BATCH", "64"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedding_service")
app = FastAPI(title="Embedding Service", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to embed")
    model: Optional[str] = Field(default=None, description="Override embedding model")
    encoding_format: Optional[str] = Field(default=None, description="Embedding encoding format (float/base64)")

    @validator("texts")
    def _validate_texts(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("texts must be non-empty")
        return v

    @validator("encoding_format")
    def _validate_encoding_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"float", "base64"}
        if v not in allowed:
            raise ValueError(f"encoding_format must be one of {sorted(allowed)}")
        return v


class EmbedResponse(BaseModel):
    vectors: List[List[float]]
    model: str
    dimensions: int
    count: int
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
    return {"status": "ok", "model": get_embedding_model(), "max_batch": MAX_BATCH}


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest, _: None = Depends(_auth_dependency)) -> EmbedResponse:
    if len(request.texts) > MAX_BATCH:
        raise HTTPException(status_code=400, detail=f"batch too large; max {MAX_BATCH}")

    start = time.time()
    try:
        # prefer_service=False to avoid circular calls (we ARE the service)
        vectors = embed_texts(
            request.texts,
            model=request.model,
            encoding_format=request.encoding_format,
            prefer_service=False,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = int((time.time() - start) * 1000)
    dims = len(vectors[0]) if vectors else 0
    response = EmbedResponse(
        vectors=vectors,
        model=request.model or get_embedding_model(),
        dimensions=dims,
        count=len(vectors),
        latency_ms=latency_ms,
    )
    logger.info(
        "embedded texts count=%d dims=%d model=%s latency_ms=%d",
        len(request.texts),
        dims,
        response.model,
        latency_ms,
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8002")))
