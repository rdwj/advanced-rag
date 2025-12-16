# Evaluator Service

FastAPI microservice for evaluating RAG answer quality using LLM-based assessment.

Part of [Advanced RAG Services](../README.md).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/evaluate` | POST | Evaluate answer quality |

### Evaluate Request

```json
{
  "question": "What is the capital of France?",
  "answer": "The capital of France is Paris.",
  "plan": {},       // optional: chunking plan used
  "keywords": []    // optional: expected keywords
}
```

### Evaluate Response

```json
{
  "score": 0.95,
  "feedback": "Answer is accurate and complete.",
  "suggested_plan": null,  // optional: suggested improvements
  "model": "gpt-4o-mini",
  "latency_ms": 800,
  "raw": null  // optional: raw model output
}
```

## Local Development

```bash
cd services/evaluator_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
export OPENAI_EVAL_MODEL="gpt-4o-mini"

uvicorn app:app --host 0.0.0.0 --port 8004 --reload
```

## Container Build

Build from within the `evaluator_service` directory (self-contained):

```bash
cd services/evaluator_service

# Local build
podman build -t evaluator-service:local -f Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build:
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='.git' . ec2-dev:~/builds/evaluator-service/
ssh ec2-dev 'cd ~/builds/evaluator-service && podman build -t evaluator-service:latest -f Containerfile .'
```

## OpenShift Deployment

### Push to OpenShift Registry

```bash
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
OC_TOKEN=$(oc whoami -t)
podman login -u unused -p ${OC_TOKEN} ${REGISTRY} --tls-verify=false
podman tag evaluator-service:latest ${REGISTRY}/advanced-rag/evaluator-service:latest
podman push --tls-verify=false ${REGISTRY}/advanced-rag/evaluator-service:latest
```

### Deploy

```bash
# Update secret with real API key
oc create secret generic evaluator-service-secrets \
  -n advanced-rag \
  --from-env-file=.env \
  --dry-run=client -o yaml | oc apply -f -

# Apply deployment
oc apply -f manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/evaluator-service -n advanced-rag --timeout=120s
```

### Verify

```bash
EVAL_URL=$(oc get route evaluator-service -n advanced-rag -o jsonpath='{.spec.host}')
curl -s "https://${EVAL_URL}/healthz" | jq .
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required) |
| `OPENAI_EVAL_MODEL` | `gpt-4.1-mini` | LLM model for evaluation |
| `AUTH_TOKEN` | - | Optional: require auth token |

## Internal Service URL

```
http://evaluator-service.advanced-rag.svc.cluster.local:8000
```
