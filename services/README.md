# Services

This directory contains the microservices that power the Advanced RAG pipeline. Each service is deployable independently to OpenShift and communicates via HTTP APIs.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            External Clients                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           vector-gateway                                     │
│                    (Unified search & storage API)                           │
│                         POST /search, /upsert                               │
└─────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ embedding-svc   │  │  rerank-svc     │  │   Milvus        │
│  POST /embed    │  │  POST /rerank   │  │ (Vector Store)  │
└─────────────────┘  └─────────────────┘  └─────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   plan-svc      │  │  chunker-svc    │  │ evaluator-svc   │
│  POST /plan     │  │  POST /chunk    │  │ POST /evaluate  │
│ (LLM Planning)  │  │   (Go binary)   │  │  (QA Scoring)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Services

| Service | Language | Port | Endpoint | Description |
|---------|----------|------|----------|-------------|
| **chunker_service** | Go | 8080 | `POST /chunk` | Sliding-window text chunking with configurable modes |
| **plan_service** | Python | 8000 | `POST /plan` | LLM-generated chunking plans based on document analysis |
| **embedding_service** | Python | 8002 | `POST /embed` | Batch text embeddings (OpenAI, Cohere, vLLM, TEI) |
| **rerank_service** | Python | 8003 | `POST /rerank` | Result reranking (Cohere, Jina) |
| **evaluator_service** | Python | 8004 | `POST /evaluate` | QA answer quality evaluation with feedback |
| **vector_gateway** | Python | 8005 | `POST /search`, `/upsert` | Unified vector store abstraction (Milvus, memory) |

All services expose a `GET /healthz` endpoint for health checks.

## Shared Library: rag_core

The `rag_core/` directory contains shared Python code used by multiple services (embedding, reranking, config utilities). Import via:

```python
from rag_core import embed_texts, rerank_documents, get_embedding_model
```

## Build Types

Services fall into two categories based on their build context:

### Self-Contained Services
Build from their own directory (no external dependencies):
- `chunker_service` (Go)
- `plan_service`
- `evaluator_service`

```bash
cd chunker_service
podman build --platform linux/amd64 -t chunker-service:latest -f Containerfile .
```

### Root-Context Services
Require `rag_core` library (build from `services/` directory):
- `embedding_service`
- `rerank_service`
- `vector_gateway`

```bash
cd services
podman build --platform linux/amd64 -t embedding-service:latest -f embedding_service/Containerfile .
```

## Quick Start

### Using the Makefile (Recommended)

```bash
# Full pipeline: build, push, deploy all services
make all

# Or step by step:
make build-all      # Build all services on ec2-dev
make push-all       # Push images to OpenShift registry
make deploy-all     # Apply manifests and rollout

# Single service operations
make build-plan     # Build plan service only
make deploy-plan    # Deploy plan service only
make plan-full      # Build, push, and deploy plan service

# Operations
make status         # Check health of all services
make rollout-all    # Restart all deployments
make logs-plan      # Tail logs for plan service
make pods           # List pods in namespace
make clean          # Clean remote build directories
```

### Prerequisites

1. **OpenShift Login**: `oc login <cluster-url>`
2. **SSH Access**: `ssh ec2-dev` configured for remote builds
3. **Secrets**: Required secrets created in `advanced-rag` namespace

### Manual Build & Deploy

```bash
# Build locally (Mac users: use remote build instead)
cd services
podman build --platform linux/amd64 -t embedding-service:latest -f embedding_service/Containerfile .

# Push to OpenShift registry
REGISTRY=$(oc registry info)
podman tag embedding-service:latest $REGISTRY/advanced-rag/embedding-service:latest
podman push --tls-verify=false $REGISTRY/advanced-rag/embedding-service:latest

# Deploy
oc apply -f embedding_service/manifests/ -n advanced-rag
oc rollout restart deployment/embedding-service -n advanced-rag
```

## API Reference

### Chunker Service

**POST /chunk** - Split text into chunks

```json
// Request
{
  "text": "Document content...",
  "plan": {
    "window_size": 200,
    "overlap": 40,
    "mode": "tokens"
  },
  "meta": {
    "file_name": "doc.pdf",
    "file_path": "/docs/doc.pdf"
  }
}

// Response: Array of chunks
[
  {
    "chunk_id": "...",
    "text": "chunk content",
    "chunk_index": 0,
    "file_name": "doc.pdf",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Plan Service

**POST /plan** - Generate chunking plan from document

```json
// Request
{
  "text": "Document sample or full text...",
  "meta": {"file_name": "doc.pdf", "mime_type": "application/pdf"}
}

// Response
{
  "plan": {
    "window_size": 300,
    "overlap": 60,
    "mode": "tokens",
    "break_on_headings": true
  },
  "model": "gpt-4",
  "latency_ms": 1234
}
```

### Embedding Service

**POST /embed** - Generate embeddings for texts

```json
// Request
{
  "texts": ["Hello world", "Another text"],
  "model": "text-embedding-3-small"  // optional override
}

// Response
{
  "vectors": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "count": 2,
  "latency_ms": 150
}
```

### Rerank Service

**POST /rerank** - Rerank documents by relevance

```json
// Request
{
  "query": "search query",
  "documents": ["doc1 text", "doc2 text", "doc3 text"],
  "top_k": 2  // optional
}

// Response
{
  "indices": [2, 0],  // reranked order
  "model": "rerank-english-v3.0",
  "latency_ms": 200
}
```

### Evaluator Service

**POST /evaluate** - Evaluate RAG answer quality

```json
// Request
{
  "question": "What is X?",
  "answer": "X is...",
  "plan": {"window_size": 200},  // optional context
  "keywords": ["expected", "terms"]  // optional
}

// Response
{
  "score": 0.85,
  "feedback": "Answer covers main points but...",
  "suggested_plan": {"window_size": 300},  // if improvement suggested
  "model": "gpt-4",
  "latency_ms": 2000
}
```

### Vector Gateway

**POST /upsert** - Store documents with embeddings

```json
// Request
{
  "documents": [
    {
      "doc_id": "doc-1",  // optional
      "text": "Document content",
      "metadata": {"file_name": "doc.pdf", "page": 1}
    }
  ],
  "collection": "my_collection"  // optional
}

// Response
{
  "inserted": 1,
  "total": 100,
  "backend": "milvus",
  "collection": "my_collection"
}
```

**POST /search** - Hybrid search with optional reranking

```json
// Request
{
  "query": "search query",
  "collection": "my_collection",
  "top_k": 5,
  "context_window": 2,  // include surrounding chunks
  "filters": {
    "file_name": "specific.pdf",
    "file_pattern": "DMC-*",
    "mime_type": "application/pdf"
  }
}

// Response
{
  "hits": [
    {
      "doc_id": "chunk-123",
      "text": "matching content...",
      "score": 0.92,
      "metadata": {...},
      "surrounding_chunks": [...]
    }
  ],
  "count": 5,
  "latency_ms": 150,
  "backend": "milvus",
  "collection": "my_collection",
  "reranked": true
}
```

**GET /collections** - List available collections

**GET /collections/{name}/stats** - Get collection statistics

## Environment Variables

### Common to All Services
| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_TOKEN` | Optional bearer token for auth | None (disabled) |
| `PORT` | HTTP port | Service-specific |

### Embedding Service
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `EMBEDDING_API_KEY` | Override for embedding API | `OPENAI_API_KEY` |
| `EMBEDDING_BASE_URL` | Custom embedding endpoint | OpenAI default |
| `EMBEDDING_MODEL` | Model name | `text-embedding-3-small` |
| `EMBEDDING_MAX_BATCH` | Max texts per request | 64 |

### Rerank Service
| Variable | Description | Default |
|----------|-------------|---------|
| `RERANK_PROVIDER` | Provider: `cohere`, `jina`, `none` | `cohere` |
| `RERANK_API_KEY` | Provider API key | Required |
| `RERANK_MODEL` | Model name | Provider default |
| `COHERE_API_KEY` | Cohere-specific key | Fallback |

### Plan Service
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | LLM API key | Required |
| `PLAN_MODEL` | LLM model for planning | `gpt-4` |

### Evaluator Service
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | LLM API key | Required |
| `EVAL_MODEL` | LLM model for evaluation | `gpt-4` |

### Vector Gateway
| Variable | Description | Default |
|----------|-------------|---------|
| `GATEWAY_BACKEND` | Backend: `milvus`, `memory` | `milvus` |
| `MILVUS_HOST` | Milvus server host | Required for milvus |
| `MILVUS_PORT` | Milvus server port | 19530 |
| `MILVUS_USER` | Milvus username | None |
| `MILVUS_PASSWORD` | Milvus password | None |
| `MILVUS_COLLECTION` | Default collection | `rag_gateway` |
| `MILVUS_DIM` | Vector dimensions | 1536 |
| `GATEWAY_MAX_DOCS` | Memory backend limit | 10000 |
| `RERANK_SERVICE_URL` | Rerank service URL | Internal cluster URL |

## Internal Service URLs

When deployed to OpenShift, services communicate via internal cluster DNS:

```bash
http://chunker-service.advanced-rag.svc.cluster.local:8080
http://plan-service.advanced-rag.svc.cluster.local:8000
http://embedding-service.advanced-rag.svc.cluster.local:8002
http://rerank-service.advanced-rag.svc.cluster.local:8003
http://evaluator-service.advanced-rag.svc.cluster.local:8004
http://vector-gateway.advanced-rag.svc.cluster.local:8005
```

## Local Development

1. **Set up Python environment:**
   ```bash
   cd services
   python -m venv .venv
   source .venv/bin/activate
   pip install -r embedding_service/requirements.txt
   ```

2. **Run a service locally:**
   ```bash
   # Copy and configure .env
   cp embedding_service/.env.example embedding_service/.env
   # Edit with your API keys

   # Run
   cd embedding_service
   PYTHONPATH=.. python app.py
   ```

3. **Test endpoints:**
   ```bash
   # Health check
   curl http://localhost:8002/healthz

   # Embed texts
   curl -X POST http://localhost:8002/embed \
     -H "Content-Type: application/json" \
     -d '{"texts": ["Hello world"]}'
   ```

## Testing

Run tests with pytest from the project root:

```bash
cd /path/to/advanced-rag
PYTHONPATH="pipelines:services" pytest pipelines/tests/
```

## Troubleshooting

### Service won't start
- Check logs: `oc logs deployment/<service-name> -n advanced-rag`
- Verify secrets exist: `oc get secrets -n advanced-rag`
- Check environment variables in deployment

### Build fails
- Ensure `--platform linux/amd64` for Mac builds
- For rag_core services, build from `services/` directory
- Check remote build host connectivity: `ssh ec2-dev`

### Connection refused between services
- Verify service is running: `oc get pods -n advanced-rag`
- Check service DNS: `oc get svc -n advanced-rag`
- Test from within cluster: `oc debug deployment/<service>`

### Milvus connection issues
- Verify Milvus is running: `oc get pods -n milvus`
- Check connection env vars: `MILVUS_HOST`, `MILVUS_PORT`
- Test connectivity: `oc exec -it <pod> -- curl milvus:19530`
