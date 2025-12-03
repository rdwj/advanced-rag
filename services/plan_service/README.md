# Plan Service

FastAPI microservice that uses LLM to generate optimal chunking plans based on document content and metadata.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/plan` | POST | Generate chunking plan |

### Plan Request

```json
{
  "text": "Document sample or full text...",
  "meta": {
    "file_name": "document.pdf",
    "mime_type": "application/pdf"
  },
  "profile": null  // optional: routing profile (unused)
}
```

### Plan Response

```json
{
  "plan": {
    "window_size": 200,
    "overlap": 40,
    "mode": "tokens",
    "break_on_headings": true
  },
  "model": "gpt-4o-mini",
  "latency_ms": 1200
}
```

## Local Development

```bash
cd services/plan_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Container Build

Build from within the `plan_service` directory (self-contained):

```bash
cd services/plan_service

# Local build
podman build -t plan-service:local -f Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build:
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' . ec2-dev:~/builds/plan-service/
ssh ec2-dev 'cd ~/builds/plan-service && podman build -t plan-service:latest -f Containerfile .'
```

## OpenShift Deployment

### Push to OpenShift Registry

```bash
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
OC_TOKEN=$(oc whoami -t)
podman login -u unused -p ${OC_TOKEN} ${REGISTRY} --tls-verify=false
podman tag plan-service:latest ${REGISTRY}/advanced-rag/plan-service:latest
podman push --tls-verify=false ${REGISTRY}/advanced-rag/plan-service:latest
```

### Deploy

```bash
# Update secret with real API key
oc create secret generic plan-service-secrets \
  -n advanced-rag \
  --from-env-file=.env \
  --dry-run=client -o yaml | oc apply -f -

# Apply deployment
oc apply -f manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/plan-service -n advanced-rag --timeout=120s
```

### Verify

```bash
PLAN_URL=$(oc get route plan-service -n advanced-rag -o jsonpath='{.spec.host}')
curl -s "https://${PLAN_URL}/healthz" | jq .
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required) |
| `PLAN_MODEL` | `gpt-4.1-mini` | LLM model for plan generation |
| `AUTH_TOKEN` | - | Optional: require auth token |

## Internal Service URL

```
http://plan-service.advanced-rag.svc.cluster.local:8000
```

## File Structure

```
services/plan_service/
├── app.py              # FastAPI application
├── lib/                # Self-contained library modules
│   ├── __init__.py
│   ├── config.py       # Configuration and client setup
│   └── plan.py         # Core planning logic
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
