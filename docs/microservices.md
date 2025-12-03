# Microservices Guide

This project includes several deployable microservices for the RAG pipeline.

## Service Overview

| Service | Language | Port | Endpoint | Description |
|---------|----------|------|----------|-------------|
| `chunker-service` | Go | 8080 | `POST /chunk` | Sliding-window text chunking |
| `plan-service` | Python | 8000 | `POST /plan` | LLM-generated ChunkingPlan |
| `embedding-service` | Python | 8000 | `POST /embed` | Batch embeddings (OpenAI/OSS) |
| `rerank-service` | Python | 8000 | `POST /rerank` | Rerank provider abstraction |
| `evaluator-service` | Python | 8000 | `POST /evaluate` | QA scoring with JSON feedback |
| `vector-gateway` | Python | 8005 | `POST /search`, `POST /upsert` | Vector store abstraction |

All services expose `/healthz` for health checks.

## Service Structure

Python services follow a consistent structure:

```
services/<name>/
├── app.py              # FastAPI entrypoint
├── lib/                # Business logic modules
│   └── config.py       # Configuration
├── Containerfile       # Container definition
├── README.md           # Service documentation
├── requirements.txt    # Dependencies
└── manifests/          # OpenShift deployment YAML
```

The Go chunker service:

```
services/chunker_service/
├── cmd/
│   ├── chunker/        # CLI entrypoint
│   └── chunker-server/ # HTTP server entrypoint
├── pkg/chunking/       # Core chunking logic
├── Containerfile
├── go.mod
└── manifests/
```

Shared Python library:

```
services/rag_core/
├── __init__.py         # Re-exports embed_texts, embed_query, rerank functions
├── config.py           # Configuration functions (get_embedding_client, etc.)
├── embed.py            # Embedding implementation
├── rerank.py           # Reranking implementation
├── models.py           # Shared data models
├── token_utils.py      # Token counting utilities
└── providers/          # Provider-specific implementations
```

## Building Services

### Using the Makefile (Recommended)

The `services/Makefile` handles remote builds on ec2-dev for OpenShift compatibility:

```bash
cd services

# Build all services
make build-all

# Build a single service
make build-embedding
make build-plan
make build-chunker

# Push all to OpenShift registry
make push-all

# Deploy all
make deploy-all

# Check health
make status
```

### Container Builds (Local)

```bash
cd services

# Self-contained services (chunker, plan, evaluator)
# Build from their own directory
cd chunker_service
podman build --platform linux/amd64 -t chunker-service:latest -f Containerfile .

# Services requiring rag_core (embedding, rerank, vector-gateway)
# Build from services/ directory
cd ..
podman build --platform linux/amd64 -t embedding-service:latest -f embedding_service/Containerfile .
podman build --platform linux/amd64 -t rerank-service:latest -f rerank_service/Containerfile .
podman build --platform linux/amd64 -t vector-gateway:latest -f vector_gateway/Containerfile .
```

### Local Development

```bash
# Python service
cd services/plan_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py

# Go chunker
cd services/chunker_service
go run ./cmd/chunker-server
```

## OpenShift Deployment

### Using the Makefile

```bash
cd services

# Full deployment (build, push, deploy)
make all

# Or step by step
make build-all
make push-all
make deploy-all

# Restart without rebuilding
make rollout-all
```

### Manual Deployment

```bash
# Deploy a service
oc apply -f services/vector_gateway/manifests/ -n advanced-rag

# Wait for rollout
oc wait --for=condition=Available deployment/vector-gateway -n advanced-rag --timeout=120s
```

### Internal Service URLs

Services communicate internally via cluster DNS:

```bash
export CHUNKER_SERVICE_URL=http://chunker-service.advanced-rag.svc.cluster.local:8080
export PLAN_SERVICE_URL=http://plan-service.advanced-rag.svc.cluster.local:8000
export EMBEDDING_SERVICE_URL=http://embedding-service.advanced-rag.svc.cluster.local:8000
export VECTOR_GATEWAY_URL=http://vector-gateway.advanced-rag.svc.cluster.local:8005
```

## Service Fallback Pattern

Python pipeline modules check for `*_SERVICE_URL` environment variables. If set, they call the service; otherwise, they fall back to local execution:

- `CHUNKER_SERVICE_URL` → calls service, else runs `bin/chunker` CLI
- `PLAN_SERVICE_URL` → calls service, else uses local `plan.py`
- `EMBEDDING_SERVICE_URL` → calls service, else uses OpenAI directly

This allows running the pipeline both locally (for development) and in OpenShift (for production).

## Configuration

Each service uses environment variables for configuration. See the service-specific README files for details.

### Secret Management

**IMPORTANT**: Service manifests include Secret resources with placeholder values (`REPLACE_WITH_ACTUAL_API_KEY`). You MUST create/update secrets with real API keys before deploying.

Create secrets before applying manifests:

```bash
# Required for plan-service, embedding-service, evaluator-service, vector-gateway
oc create secret generic <service>-secrets \
  --from-literal=OPENAI_API_KEY="your-openai-key" \
  -n advanced-rag

# Required for rerank-service (if using Cohere)
oc create secret generic rerank-service-secrets \
  --from-literal=COHERE_API_KEY="your-cohere-key" \
  --from-literal=RERANK_API_KEY="your-rerank-key" \
  -n advanced-rag
```

Or update existing secrets:

```bash
oc create secret generic <service>-secrets \
  --from-literal=OPENAI_API_KEY="your-key" \
  -n advanced-rag --dry-run=client -o yaml | oc apply -f -
```

After updating secrets, restart deployments:

```bash
oc rollout restart deployment/<service> -n advanced-rag
```

### Common Variables

- `OPENAI_API_KEY` - Required for LLM operations
- `EMBEDDING_MODEL` - Embedding model to use
- `VECTOR_BACKEND` - `milvus`, `pgvector`, or `meilisearch`
- `COHERE_API_KEY` - Required for Cohere reranking
