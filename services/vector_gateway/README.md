# Vector Gateway

FastAPI microservice providing a REST API for vector operations backed by Milvus. Exposes `/search` and `/upsert` endpoints with embedding generation via OpenAI or a configurable embedding service.

Part of [Advanced RAG Services](../README.md).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check - returns `{status, backend, count}` |
| `/upsert` | POST | Insert/update documents with embeddings |
| `/search` | POST | Semantic search over stored documents |

### Upsert Request

```json
{
  "documents": [
    {"doc_id": "id1", "text": "hello world", "metadata": {"source": "test"}}
  ],
  "model": "text-embedding-3-small"
}
```

### Search Request

```json
{
  "query": "hello",
  "top_k": 5,
  "model": "text-embedding-3-small"
}
```

## Local Development

```bash
cd services/vector_gateway
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set PYTHONPATH to include rag_pipeline modules
export PYTHONPATH="$(cd ../.. && pwd)/python"
export OPENAI_API_KEY="sk-..."

# For Milvus backend (default)
export MILVUS_HOST="localhost"
export MILVUS_PORT="19530"

# Or use memory backend for testing
export GATEWAY_BACKEND="memory"

uvicorn app:app --host 0.0.0.0 --port 8005 --reload
```

## Container Build

Build from the `adaptive-semantic-chunking` directory (requires access to `python/` for rag_pipeline modules):

```bash
cd /path/to/adaptive-semantic-chunking

# Local build (for testing)
podman build -t vector-gateway:local -f services/vector_gateway/Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build
# Option 1: Use /build-remote slash command
# Option 2: Build on ec2-dev manually:
#   rsync -avz --exclude='.venv' --exclude='__pycache__' . ec2-dev:~/build-context/
#   ssh ec2-dev 'cd ~/build-context && podman build -t quay.io/rh-aiservices-bu/vector-gateway:latest -f services/vector_gateway/Containerfile .'
#   ssh ec2-dev 'podman push quay.io/rh-aiservices-bu/vector-gateway:latest'
```

## OpenShift Deployment

### Prerequisites

- Milvus deployed in `advanced-rag` namespace (see `milvus/OPENSHIFT_DEPLOYMENT.md`)
- OpenAI API key or embedding service deployed
- Container image pushed to accessible registry

### Deploy

```bash
# Set your OpenAI API key in the secret
oc create secret generic vector-gateway-secrets \
  -n advanced-rag \
  --from-literal=OPENAI_API_KEY="sk-your-actual-key" \
  --dry-run=client -o yaml | oc apply -f -

# Apply deployment manifests
oc apply -f services/vector_gateway/manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/vector-gateway -n advanced-rag --timeout=120s

# Get route URL
oc get route vector-gateway -n advanced-rag -o jsonpath='{.spec.host}'
```

### Verify

```bash
GATEWAY_URL=$(oc get route vector-gateway -n advanced-rag -o jsonpath='{.spec.host}')

# Health check
curl -s "https://${GATEWAY_URL}/healthz" | jq .

# Upsert a test document
curl -X POST "https://${GATEWAY_URL}/upsert" \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"doc_id": "test-1", "text": "Milvus is a vector database for AI applications.", "metadata": {"source": "test"}}
    ]
  }'

# Search
curl -X POST "https://${GATEWAY_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Milvus?", "top_k": 3}'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_BACKEND` | `milvus` | Backend type: `milvus` or `memory` |
| `GATEWAY_REQUIRE_BACKEND` | `0` | Fail if backend unavailable (`1` = yes) |
| `GATEWAY_MAX_DOCS` | `10000` | Max documents for memory backend |
| `MILVUS_HOST` | - | Milvus host address |
| `MILVUS_PORT` | `19530` | Milvus gRPC port |
| `MILVUS_COLLECTION` | `rag_gateway` | Collection name |
| `MILVUS_DIM` | `1536` | Vector dimension |
| `OPENAI_API_KEY` | - | OpenAI API key for embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `EMBEDDING_SERVICE_URL` | - | Optional: external embedding service |
| `AUTH_TOKEN` | - | Optional: require auth token |

### Authentication

If `AUTH_TOKEN` is set, requests must include:
- `Authorization: Bearer <token>` header, or
- `X-API-Key: <token>` header

## Dependencies

This service depends on `python/rag_pipeline/` modules for embedding generation and Milvus operations. Build from the repository root (not from within this directory).
