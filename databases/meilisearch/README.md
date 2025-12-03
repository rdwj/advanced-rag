# Meilisearch for Adaptive Semantic Chunking

This directory holds tooling for running Meilisearch with vector/hybrid search capabilities, wiring it to the RAG pipeline in `adaptive-semantic-chunking`.

## Deployment Options

- **Local development**: See `local/` directory - uses Podman/Docker or native binary
- **OpenShift**: See `openshift/` directory - Kustomize manifests for cluster deployment

## OpenShift Deployment

```bash
# Grant anyuid SCC (Meilisearch runs as root)
oc adm policy add-scc-to-user anyuid -z default -n advanced-rag

# Deploy using Kustomize
oc apply -k databases/meilisearch/openshift/ -n advanced-rag

# Wait for pod to be ready
oc wait --for=condition=Ready pods -l app=meilisearch -n advanced-rag --timeout=120s

# Get route URL
MEILI_URL=$(oc get route meilisearch -n advanced-rag -o jsonpath='{.spec.host}')
echo "Meilisearch URL: https://${MEILI_URL}"
```

For OpenShift, update the master key in the secret before production use:
```bash
oc create secret generic meilisearch-credentials \
  --from-literal=MEILI_MASTER_KEY="your-secure-key" \
  -n advanced-rag --dry-run=client -o yaml | oc apply -f -
oc rollout restart deployment/meilisearch -n advanced-rag
```

## Local Development

```bash
# From anywhere - script auto-detects its location
cd databases/meilisearch/local
./meili.sh start            # launch Meilisearch on :7700 with persisted data
./meili.sh stop             # stop container/process
./meili.sh destroy          # stop + remove container (keeps data)
./meili.sh status           # show current status and paths
```

Defaults:
- image: `getmeili/meilisearch:v1.16`
- data dir: `databases/meilisearch/local/data` (relative to script location)
- master key: `dev-meili-master-key` (override with `MEILI_MASTER_KEY`)
- Container runtime: prefers Podman, falls back to Docker, then native binary

## Vector Search Setup

Vector search requires configuring an embedder on your index. For user-provided embeddings (recommended for RAG):

```bash
# Configure embedder on index (replace with your embedding dimensions)
curl -X PATCH "http://localhost:7700/indexes/YOUR_INDEX/settings" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  --data-binary '{
    "embedders": {
      "default": {
        "source": "userProvided",
        "dimensions": 1536
      }
    }
  }'
```

Then add documents with `_vectors` field:
```json
[
  {
    "id": 1,
    "text": "Document content",
    "_vectors": {
      "default": {
        "embeddings": [0.1, 0.2, ...],
        "regenerate": false
      }
    }
  }
]
```

Perform hybrid search:
```bash
curl -X POST "http://localhost:7700/indexes/YOUR_INDEX/search" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-dev-meili-master-key}" \
  --data-binary '{
    "q": "search query",
    "hybrid": {
      "embedder": "default",
      "semanticRatio": 0.7
    }
  }'
```

## Pipeline env (example)

```bash
export VECTOR_BACKEND=meilisearch
export MEILI_HOST=http://127.0.0.1:7700
export MEILI_API_KEY=${MEILI_MASTER_KEY:-dev-meili-master-key}
export MEILI_INDEX=rag_chunks_meili
export MEILI_SEMANTIC_RATIO=0.6
export MEILI_RANKING_THRESHOLD=0.35
export MEILI_EMBEDDER=default
export MEILI_MANAGED_EMBEDDER=    # leave empty to supply embeddings client-side
pip install meilisearch
```

Then ingest/search as usual, e.g.:

```bash
python python/scripts/run_ingest_pipeline.py --plan-source static --window-size 512 --overlap 96 --mode tokens test_files/sample_dummy_w3.pdf
python python/scripts/run_qa_manifest.py --manifest qa_manifest_pg.json --output-dir qa_runs_meili
```

If you want Meilisearch to generate embeddings itself, set:

```bash
export MEILI_MANAGED_EMBEDDER=openAi
export MEILI_EMBEDDER_MODEL=text-embedding-3-small
export MEILI_EMBEDDER_DIM=1536
```

## Notes

- Meilisearch vector search is stable in v1.14+. Best for small/medium corpora (<5-10M docs).
- `semanticRatio` tunes full-text vs vector; start around 0.5-0.7.
- `rankingScoreThreshold` (0.3-0.5 recommended) drops weak hits for RAG.
- Typo tolerance and prefix search remain active; keep filterable attributes lean for speed.
- The script is portable - all paths are relative to the script location.
