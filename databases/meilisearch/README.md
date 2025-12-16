# Meilisearch

Fast, typo-tolerant search engine with native vector search support. Ideal for applications requiring both keyword and semantic search capabilities.

Part of [databases](../README.md).

## Features

- Lightning-fast full-text search with typo tolerance
- Native hybrid search (keyword + vector)
- Simple REST API
- Faceted search and filtering

## Local Development

### Quick Start

```bash
cd local
./meili.sh start            # Start on port 7700
./meili.sh status           # Check status
curl http://localhost:7700/health
```

### Commands

```bash
./meili.sh start    # Start Meilisearch
./meili.sh stop     # Stop container/process
./meili.sh status   # Show status and paths
./meili.sh destroy  # Stop and remove container (keeps data)
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Port | 7700 | HTTP API port |
| Master Key | `dev-meili-master-key` | Authentication key |
| Data Dir | `local/data` | Persistent data location |
| Image | `getmeili/meilisearch:v1.16` | Container image |

Override with environment variables:
```bash
MEILI_MASTER_KEY="your-key" ./meili.sh start
```

## OpenShift Deployment

### Quick Deploy

```bash
# Grant anyuid SCC (Meilisearch runs as root)
oc adm policy add-scc-to-user anyuid -z default -n your-namespace

# Deploy using Kustomize
oc apply -k openshift/ -n your-namespace

# Wait for pod
oc wait --for=condition=Ready pods -l app=meilisearch -n your-namespace --timeout=120s

# Get route URL
MEILI_URL=$(oc get route meilisearch -n your-namespace -o jsonpath='{.spec.host}')
echo "Meilisearch URL: https://${MEILI_URL}"
```

### Production Configuration

Update the master key before production use:

```bash
oc create secret generic meilisearch-credentials \
  --from-literal=MEILI_MASTER_KEY="your-secure-key-here" \
  -n your-namespace --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/meilisearch -n your-namespace
```

## Usage Examples

### Create Index

```bash
curl -X POST "http://localhost:7700/indexes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  -d '{"uid": "documents", "primaryKey": "id"}'
```

### Configure Vector Search

```bash
# Set up embedder for user-provided vectors (e.g., 1536 dimensions for OpenAI)
curl -X PATCH "http://localhost:7700/indexes/documents/settings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  -d '{
    "embedders": {
      "default": {
        "source": "userProvided",
        "dimensions": 1536
      }
    }
  }'
```

### Add Documents with Vectors

```bash
curl -X POST "http://localhost:7700/indexes/documents/documents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  -d '[
    {
      "id": 1,
      "title": "Document Title",
      "content": "Document content here",
      "_vectors": {
        "default": {
          "embeddings": [0.1, 0.2, ...],
          "regenerate": false
        }
      }
    }
  ]'
```

### Keyword Search

```bash
curl -X POST "http://localhost:7700/indexes/documents/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  -d '{"q": "search query", "limit": 10}'
```

### Hybrid Search (Keyword + Vector)

```bash
curl -X POST "http://localhost:7700/indexes/documents/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  -d '{
    "q": "search query",
    "hybrid": {
      "embedder": "default",
      "semanticRatio": 0.7
    },
    "limit": 10
  }'
```

### Python Client

```python
import meilisearch

# Connect
client = meilisearch.Client(
    "http://localhost:7700",
    api_key="dev-meili-master-key"
)

# Get index
index = client.index("documents")

# Add documents
index.add_documents([
    {"id": 1, "title": "Doc 1", "content": "Content here"}
])

# Search
results = index.search("query")
```

## Environment Variables

For applications connecting to Meilisearch:

```bash
export MEILI_HOST=http://localhost:7700
export MEILI_API_KEY=dev-meili-master-key
export MEILI_INDEX=documents
export MEILI_SEMANTIC_RATIO=0.6      # Balance between keyword and vector
export MEILI_RANKING_THRESHOLD=0.35  # Minimum score threshold
```

## Notes

- Vector search stable in v1.14+
- Best for small/medium datasets (<5-10M documents)
- `semanticRatio`: 0.0 = pure keyword, 1.0 = pure vector (0.5-0.7 recommended)
- `rankingScoreThreshold`: Filters low-confidence results (0.3-0.5 recommended)
- Typo tolerance and prefix search are always active
- Keep filterable attributes minimal for best performance
