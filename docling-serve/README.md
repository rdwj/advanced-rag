# Docling-Serve on OpenShift

Document conversion service (PDF to Markdown/JSON) for RAG pipelines. Supports integration with [granite-vision](../models/granite-vision/) for automatic image descriptions.

## Architecture

```
                                    OpenShift Cluster
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │   ┌─────────────────────────┐      ┌─────────────────────────────┐ │
    │   │   docling-serve         │      │   granite-vision            │ │
    │   │   Namespace             │      │   (models/ directory)       │ │
    │   │                         │      │                             │ │
    │   │  ┌───────────────────┐  │ HTTP │  ┌───────────────────────┐  │ │
    │   │  │ docling-serve     │──┼──────┼─▶│ granite-vision        │  │ │
    │   │  │ (CPU or GPU)      │  │      │  │ (vLLM + GPU)          │  │ │
    │   │  │                   │  │      │  │                       │  │ │
    │   │  │ - PDF parsing     │  │      │  │ - Image analysis      │  │ │
    │   │  │ - OCR             │  │      │  │ - Description gen     │  │ │
    │   │  │ - Table detection │  │      │  │                       │  │ │
    │   │  └───────────────────┘  │      │  └───────────────────────┘  │ │
    │   └─────────────────────────┘      └─────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
docling-serve/
├── README.md                         # This file
└── manifests/
    ├── base/                         # Common resources
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── route.yaml
    └── overlays/
        ├── cpu/                      # CPU-only (dev/test)
        │   ├── kustomization.yaml
        │   └── namespace.yaml
        └── gpu/                      # GPU-enabled (production)
            ├── kustomization.yaml
            └── namespace.yaml
```

## Prerequisites

- OpenShift cluster
- For GPU overlay: GPU nodes labeled with `node-role.kubernetes.io/worker-gpu: ""`
- For VLM integration: Deploy [granite-vision](../models/granite-vision/) first

## Quick Start

### CPU Deployment (Dev/Test)

For development without GPU or VLM support:

```bash
# Deploy
oc apply -k manifests/overlays/cpu

# Wait for rollout
oc wait --for=condition=Available deployment/docling-serve -n docling-serve --timeout=120s

# Get route URL
oc get route docling-serve -n docling-serve -o jsonpath='{.spec.host}'
```

### GPU Deployment (Production)

For production with GPU acceleration and VLM integration:

```bash
# First, deploy granite-vision (optional, for image descriptions)
oc apply -k ../models/granite-vision/manifests/overlays/default

# Deploy GPU-enabled docling-serve
oc apply -k manifests/overlays/gpu

# Wait for rollout
oc wait --for=condition=Available deployment/docling-serve -n docling-serve --timeout=180s
```

### Custom Namespace

Create a new overlay for your target namespace:

```bash
mkdir -p manifests/overlays/my-namespace
cat > manifests/overlays/my-namespace/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: my-namespace
resources:
- ../../base
- namespace.yaml
images:
- name: ghcr.io/docling-project/docling-serve-cpu
  newName: ghcr.io/docling-project/docling-serve-cpu
EOF

cat > manifests/overlays/my-namespace/namespace.yaml <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
EOF

oc apply -k manifests/overlays/my-namespace
```

## CPU vs GPU Comparison

| Aspect | CPU Overlay | GPU Overlay |
|--------|-------------|-------------|
| Image | `docling-serve-cpu` | `docling-serve-cu126` |
| Memory | 4-8Gi | 8-16Gi |
| GPU | None | 1x nvidia.com/gpu |
| VLM Support | No | Yes (remote services enabled) |
| Route Timeout | 300s | 600s |
| Use Case | Dev/test, simple text PDFs | Production, image descriptions |

## Usage

### Basic PDF to Markdown

```bash
DOCLING_HOST="https://$(oc get route docling-serve -n docling-serve -o jsonpath='{.spec.host}')"

curl -X POST "${DOCLING_HOST}/v1/convert/file/async" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@document.pdf" \
  -F "from_formats=pdf" \
  -F "to_formats=md"
```

### PDF with Picture Descriptions (GPU + granite-vision)

```bash
DOCLING_HOST="https://$(oc get route docling-serve -n docling-serve -o jsonpath='{.spec.host}')"

# Configure VLM API (internal cluster URL)
PICTURE_API='{
  "url": "http://granite-vision.granite-vision.svc.cluster.local:8000/v1/chat/completions",
  "headers": {},
  "params": {"model": "granite-vision"},
  "timeout": 120.0,
  "concurrency": 1,
  "prompt": "Describe this image briefly for document understanding."
}'

# Submit async conversion
RESPONSE=$(curl -s -X POST "${DOCLING_HOST}/v1/convert/file/async" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@document.pdf" \
  -F "from_formats=pdf" \
  -F "to_formats=json" \
  -F "include_images=true" \
  -F "do_picture_description=true" \
  -F "picture_description_api=${PICTURE_API}")

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')

# Poll for completion
while true; do
  STATUS=$(curl -s "${DOCLING_HOST}/v1/status/poll/${TASK_ID}" | jq -r '.task_status')
  echo "Status: $STATUS"
  [ "$STATUS" = "success" ] || [ "$STATUS" = "failure" ] && break
  sleep 5
done

# Get result
curl -s "${DOCLING_HOST}/v1/result/${TASK_ID}" > result.json
```

### Conversion Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `files` | File | Document to convert |
| `from_formats` | String | Input: `pdf`, `docx`, `pptx`, `html`, `image` |
| `to_formats` | String | Output: `md`, `json`, `html`, `text`, `doctags` |
| `page_range` | Tuple | Page range (e.g., `1`, `10`) |
| `include_images` | Boolean | Include base64 images |
| `do_picture_description` | Boolean | Generate AI descriptions |
| `picture_description_api` | JSON | VLM API configuration |
| `do_ocr` | Boolean | Enable OCR |
| `do_table_structure` | Boolean | Detect tables |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCLING_SERVE_ENABLE_UI` | `true` | Enable Swagger UI |
| `DOCLING_SERVE_ENABLE_REMOTE_SERVICES` | `false` | Enable VLM calls (GPU overlay sets `true`) |

### Resource Requirements

| Overlay | CPU | Memory | GPU |
|---------|-----|--------|-----|
| CPU | 1-4 | 4-8Gi | - |
| GPU | 1-4 | 8-16Gi | 1 |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/convert/file` | POST | Sync conversion |
| `/v1/convert/file/async` | POST | Async conversion |
| `/v1/status/poll/{task_id}` | GET | Poll task status |
| `/v1/result/{task_id}` | GET | Get result |
| `/openapi.json` | GET | API spec |

## Production Hardening

The base manifests include comments for production enhancements:

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: docling-serve-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: docling-serve
```

### Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: docling-serve-egress
spec:
  podSelector:
    matchLabels:
      app: docling-serve
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          app.kubernetes.io/name: granite-vision
    ports:
    - port: 8000
```

### Resource Quota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: docling-serve-quota
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 16Gi
    limits.cpu: "8"
    limits.memory: 32Gi
```

## Troubleshooting

### Pod Pending
```bash
# Check GPU availability
oc get nodes -l node-role.kubernetes.io/worker-gpu -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable."nvidia\.com/gpu"
```

### Picture Descriptions Not Working
1. Verify `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true` (GPU overlay)
2. Check granite-vision is deployed and healthy
3. Use internal DNS: `http://granite-vision.<namespace>.svc.cluster.local:8000`

### Logs
```bash
oc logs -f deployment/docling-serve -n docling-serve
```

## RAG Pipeline Integration

### Internal Service URLs

| Service | URL |
|---------|-----|
| docling-serve | `http://docling-serve.docling-serve.svc.cluster.local:5001` |
| granite-vision | `http://granite-vision.granite-vision.svc.cluster.local:8000` |

### Workflow

1. **Ingest**: Submit documents with `do_picture_description=true`
2. **Parse**: Extract text, tables, image descriptions from JSON
3. **Chunk**: Split into semantic chunks
4. **Embed**: Generate embeddings
5. **Store**: Index in vector database

## Related Components

- [granite-vision](../models/granite-vision/) - VLM for image descriptions
- [caikit-embeddings](../models/caikit-embeddings/) - Embedding models
- [adaptive-semantic-chunking](../adaptive-semantic-chunking/) - RAG pipeline

## License

Refer to respective licenses:
- [Docling](https://github.com/DS4SD/docling)
- [IBM Granite Models](https://huggingface.co/ibm-granite)
