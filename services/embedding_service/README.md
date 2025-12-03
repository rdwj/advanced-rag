# Embedding Service

FastAPI microservice for generating text embeddings using OpenAI or compatible embedding APIs.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/embed` | POST | Generate embeddings for text batch |

### Embed Request

```json
{
  "texts": ["text 1", "text 2", "..."],
  "model": "text-embedding-3-small",  // optional override
  "encoding_format": "float"           // optional: float or base64
}
```

### Embed Response

```json
{
  "vectors": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "count": 2,
  "latency_ms": 150
}
```

## Local Development

```bash
cd services/embedding_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."

uvicorn app:app --host 0.0.0.0 --port 8002 --reload
```

## Container Build

Build from within the `embedding_service` directory (self-contained):

```bash
cd services/embedding_service

# Local build
podman build -t embedding-service:local -f Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build:
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' . ec2-dev:~/builds/embedding-service/
ssh ec2-dev 'cd ~/builds/embedding-service && podman build -t embedding-service:latest -f Containerfile .'
```

## OpenShift Deployment

### Push to OpenShift Registry

```bash
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
OC_TOKEN=$(oc whoami -t)
podman login -u unused -p ${OC_TOKEN} ${REGISTRY} --tls-verify=false
podman tag embedding-service:latest ${REGISTRY}/advanced-rag/embedding-service:latest
podman push --tls-verify=false ${REGISTRY}/advanced-rag/embedding-service:latest
```

### Deploy

```bash
# Update secret with real API key first
oc create secret generic embedding-service-secrets \
  -n advanced-rag \
  --from-env-file=.env \
  --dry-run=client -o yaml | oc apply -f -

# Apply deployment
oc apply -f manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/embedding-service -n advanced-rag --timeout=120s
```

### Verify

```bash
EMBED_URL=$(oc get route embedding-service -n advanced-rag -o jsonpath='{.spec.host}')
curl -s "https://${EMBED_URL}/healthz" | jq .
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Default embedding model |
| `EMBEDDING_MAX_BATCH` | `64` | Max texts per request |
| `AUTH_TOKEN` | - | Optional: require auth token |

## Internal Service URL

```
http://embedding-service.advanced-rag.svc.cluster.local:8000
```

## File Structure

```
services/embedding_service/
├── app.py              # FastAPI application
├── lib/                # Self-contained library modules
│   ├── __init__.py
│   ├── config.py       # Configuration and client setup
│   ├── embed.py        # Core embedding logic
│   └── token_utils.py  # Token estimation utilities
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
