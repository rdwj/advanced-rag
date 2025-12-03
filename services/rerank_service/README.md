# Rerank Service

FastAPI microservice for reranking search results using Cohere or compatible reranking APIs.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/rerank` | POST | Rerank documents by query relevance |

### Rerank Request

```json
{
  "query": "What is machine learning?",
  "documents": ["doc1 text...", "doc2 text...", "..."],
  "model": null,  // optional override
  "top_k": 5      // optional: limit results
}
```

### Rerank Response

```json
{
  "indices": [2, 0, 4, 1, 3],  // reordered indices by relevance
  "model": "rerank-english-v3.0",
  "latency_ms": 350
}
```

## Local Development

```bash
cd services/rerank_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export COHERE_API_KEY="..."
export RERANK_PROVIDER="cohere"
export RERANK_MODEL="rerank-english-v3.0"

uvicorn app:app --host 0.0.0.0 --port 8003 --reload
```

## Container Build

Build from within the `rerank_service` directory (self-contained):

```bash
cd services/rerank_service

# Local build
podman build -t rerank-service:local -f Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build:
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' . ec2-dev:~/builds/rerank-service/
ssh ec2-dev 'cd ~/builds/rerank-service && podman build -t rerank-service:latest -f Containerfile .'
```

## OpenShift Deployment

### Push to OpenShift Registry

```bash
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
OC_TOKEN=$(oc whoami -t)
podman login -u unused -p ${OC_TOKEN} ${REGISTRY} --tls-verify=false
podman tag rerank-service:latest ${REGISTRY}/advanced-rag/rerank-service:latest
podman push --tls-verify=false ${REGISTRY}/advanced-rag/rerank-service:latest
```

### Deploy

```bash
# Update secret with real API key
oc create secret generic rerank-service-secrets \
  -n advanced-rag \
  --from-env-file=.env \
  --dry-run=client -o yaml | oc apply -f -

# Apply deployment
oc apply -f manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/rerank-service -n advanced-rag --timeout=120s
```

### Verify

```bash
RERANK_URL=$(oc get route rerank-service -n advanced-rag -o jsonpath='{.spec.host}')
curl -s "https://${RERANK_URL}/healthz" | jq .
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `COHERE_API_KEY` | - | Cohere API key |
| `RERANK_API_KEY` | - | Alternative: generic rerank API key |
| `RERANK_PROVIDER` | `cohere` | Provider: cohere |
| `RERANK_MODEL` | `rerank-english-v3.0` | Reranking model |
| `RERANK_BASE_URL` | - | Optional: custom API endpoint |
| `AUTH_TOKEN` | - | Optional: require auth token |

## Internal Service URL

```
http://rerank-service.advanced-rag.svc.cluster.local:8000
```

## File Structure

```
services/rerank_service/
├── app.py              # FastAPI application
├── lib/                # Self-contained library modules
│   ├── __init__.py
│   ├── config.py       # Configuration and client setup
│   └── rerank.py       # Core reranking logic
├── requirements.txt    # Python dependencies
├── Containerfile       # Container build (self-contained)
├── manifests/
│   └── deployment.yaml # OpenShift deployment
└── README.md           # This file
```

## Notes

- Service is self-contained for future repo separation
- All dependencies are local to the service directory
- No external python/ directory required
