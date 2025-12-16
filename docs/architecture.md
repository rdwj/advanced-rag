# Adaptive Semantic Chunking / RAG Architecture

## System Overview

```
Document (PDF/MD/HTML/TXT/XML)
        |
        v
Extraction (Docling PDF→MD; fallback text read)
        |
        v
Planning (LLM: plan model OpenAI or OSS; fields: window, overlap, mode)
        |
        v
Chunking (Go CLI; sliding window)
        |
        v
Embedding (OpenAI)
        |
        v
Vector Store Insert (Milvus/PGVector/Meilisearch)
        |
        v
Retrieval (Hybrid search)
        |
        v
Answer (OpenAI chat; citation-enforced)
        |
        v
Evaluator (OpenAI eval model; JSON score/feedback; suggest plan tweaks)
        |
   iterate (<=5 rounds) back to Planning
```

## Components

### Extraction (`pipelines/rag_pipeline/extract.py`)

- PDF → Markdown via Docling (preferred); falls back to pypdf/raw text read.
- Infers MIME and basic metadata; carries docling model info when available.

### Planning (`pipelines/rag_pipeline/plan.py`)

- LLM-generated `ChunkingPlan` (window_size, overlap, mode, break_on_headings, max_chunks, notes).
- Plan model configurable per run; supports OpenAI or OSS (Together) endpoints.

### Chunking (Go) (`services/chunker_service/`)

- Sliding-window chunker with chars/tokens/lines modes
- Heading-aware chunking with `break_on_headings` option
- HTTP service or CLI interface

### Embedding (`pipelines/rag_pipeline/embed.py`)

- OpenAI embeddings with batching/truncation guards to respect context limits.
- Re-exports from `services/rag_core/` for backward compatibility.

### Vector Store (`pipelines/rag_pipeline/vector_store.py`)

- **Milvus** (default): BM25 hybrid search, RRF fusion
- **PGVector**: Dense vectors + PostgreSQL FTS with manual RRF
- **Meilisearch**: Score-based hybrid via `semanticRatio`

See [vector-stores.md](vector-stores.md) for detailed configuration.

### Reranking (`pipelines/rag_pipeline/rerank.py`)

- Provider abstraction supporting Cohere, OpenAI, or none
- Applied after hybrid search, before context assembly
- Re-exports from `services/rag_core/` for backward compatibility

### Retrieval

- Hybrid search (BM25 + dense vectors)
- RRF fusion for score normalization
- Context expansion with surrounding chunks

### Evaluation (`services/evaluator_service/`)

- JSON-based scoring with feedback
- Iterative plan refinement (max 5 rounds)

## Microservices

See [microservices.md](microservices.md) for the full service reference.

| Service | Language | Port | Purpose |
|---------|----------|------|---------|
| `chunker-service` | Go | 8080 | Sliding-window text chunking |
| `plan-service` | Python | 8000 | LLM-generated ChunkingPlan |
| `embedding-service` | Python | 8000 | Batch embeddings |
| `rerank-service` | Python | 8000 | Rerank provider abstraction |
| `evaluator-service` | Python | 8000 | QA scoring with JSON feedback |
| `vector-gateway` | Python | 8005 | Vector store abstraction |

All services expose `/healthz` for health checks.

## Environment Configuration

### Required

- `OPENAI_API_KEY` - Primary API key for LLM operations

### Vector Store Selection

- `VECTOR_BACKEND` - `milvus` (default), `pgvector`, or `meilisearch`

See [vector-stores.md](vector-stores.md) for backend-specific configuration.

### Embeddings/Rerank

- `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`
- `RERANK_PROVIDER` (`cohere`, `openai`, `none`)
- `RERANK_API_KEY`, `RERANK_MODEL`

### Microservice URLs

- `CHUNKER_SERVICE_URL`, `PLAN_SERVICE_URL`
- `EMBEDDING_SERVICE_URL`, `RERANK_SERVICE_URL`
- `EVALUATOR_SERVICE_URL`, `VECTOR_GATEWAY_URL`
