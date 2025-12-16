# Advanced RAG Kubernetes Manifests

Kustomize-based manifests for deploying Advanced RAG services to OpenShift. Contains base manifests and environment overlays for dev and customer deployments.

## Quick Start

### Prerequisites

1. OpenShift cluster access (`oc login`)
2. Target namespace created
3. Secrets configured (see Secrets section)

### Deploy

```bash
# Deploy to dev (default)
cd manifests
make deploy

# Deploy specific overlay
make deploy OVERLAY=dev NAMESPACE=advanced-rag

# Preview what will be deployed
make build

# See diff vs deployed
make diff
```

## Container Images

All images are built via GitHub Actions and pushed to GitHub Container Registry:

- `ghcr.io/rdwj/advanced-rag/chunker-service:latest`
- `ghcr.io/rdwj/advanced-rag/embedding-service:latest`
- `ghcr.io/rdwj/advanced-rag/plan-service:latest`
- `ghcr.io/rdwj/advanced-rag/evaluator-service:latest`
- `ghcr.io/rdwj/advanced-rag/rerank-service:latest`
- `ghcr.io/rdwj/advanced-rag/vector-gateway:latest`
- `ghcr.io/rdwj/advanced-rag/retrieval-mcp:latest`

Images are automatically built on push to `main` branch when service files change.

## Secrets

Each service that requires API keys needs secrets created manually:

```bash
# Embedding service (OpenAI)
oc create secret generic embedding-service-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n advanced-rag

# Plan service (OpenAI)
oc create secret generic plan-service-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n advanced-rag

# Evaluator service (OpenAI)
oc create secret generic evaluator-service-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n advanced-rag

# Rerank service (Cohere)
oc create secret generic rerank-service-secrets \
  --from-literal=COHERE_API_KEY="..." \
  --from-literal=RERANK_API_KEY="..." \
  -n advanced-rag

# Vector gateway (OpenAI for embeddings)
oc create secret generic vector-gateway-secrets \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n advanced-rag
```

## Creating a Customer Overlay

1. Copy the example overlay:
   ```bash
   cp -r overlays/example-customer overlays/acme-corp
   ```

2. Edit `overlays/acme-corp/kustomization.yaml`:
   - Set the correct namespace
   - Configure model endpoints
   - Pin image versions

3. Deploy:
   ```bash
   make deploy OVERLAY=acme-corp NAMESPACE=acme-rag
   ```

See `overlays/example-customer/README.md` for detailed customization options.

## Services

| Service | Port | Description |
|---------|------|-------------|
| chunker-service | 8080 | Go-based sliding window text chunker |
| embedding-service | 8000 | Text embedding generation |
| plan-service | 8000 | LLM-based chunking plan generation |
| evaluator-service | 8000 | RAG answer quality evaluation |
| rerank-service | 8000 | Search result reranking |
| vector-gateway | 8000 | REST API for Milvus vector operations |
| retrieval-mcp | 8080 | MCP server for RAG retrieval |

## Makefile Commands

```bash
make help          # Show all commands
make build         # Preview manifests (kustomize build)
make deploy        # Deploy to cluster
make diff          # Show diff vs deployed
make rollout       # Restart all deployments
make status        # Check service health
make pods          # List pods
make logs-<svc>    # Follow logs (e.g., make logs-vector-gateway)
make clean         # Delete all resources
```
