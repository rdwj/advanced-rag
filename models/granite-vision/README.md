# Granite Vision 3.2 2B

IBM Granite Vision Language Model deployed via vLLM on OpenShift. Used for image understanding and generating descriptions in the docling-serve pipeline.

## Model Details

| Property | Value |
|----------|-------|
| Model | `ibm-granite/granite-vision-3.2-2b` |
| Parameters | 2B |
| Context Length | 65,536 tokens (required for base64 images) |
| Runtime | vLLM v0.6.6.post1 |
| GPU | 1x NVIDIA GPU required |

## Deployment

### Quick Start

```bash
# Deploy to default namespace (granite-vision)
oc apply -k manifests/overlays/default

# Wait for rollout
oc wait --for=condition=Available deployment/granite-vision -n granite-vision --timeout=600s

# Get route URL
oc get route granite-vision -n granite-vision -o jsonpath='{.spec.host}'
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
EOF

oc apply -k manifests/overlays/my-namespace
```

## API Usage

### OpenAI-Compatible Chat Completion

```bash
ROUTE=$(oc get route granite-vision -n granite-vision -o jsonpath='{.spec.host}')

curl -X POST "https://${ROUTE}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-vision",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Describe this image in detail."},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ]
      }
    ],
    "max_tokens": 500
  }'
```

### Python Client

```python
from openai import OpenAI
import base64

client = OpenAI(
    base_url="https://granite-vision-granite-vision.apps.your-cluster.com/v1",
    api_key="not-required"  # vLLM doesn't require auth by default
)

# Load and encode image
with open("image.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="granite-vision",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]
        }
    ],
    max_tokens=500
)
print(response.choices[0].message.content)
```

## Integration with Docling

When using with docling-serve for document conversion with image descriptions:

1. Deploy granite-vision first
2. Configure docling-serve with:
   - `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true`
   - `DOCLING_VLM_ENDPOINT=http://granite-vision.<namespace>.svc.cluster.local:8000/v1`

See the [docling-serve documentation](../../docling-serve/README.md) for full integration details.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  docling-serve  │────▶│  granite-vision  │────▶│  GPU Node      │
│  (PDF → MD)     │     │  (vLLM)          │     │  (inference)   │
└─────────────────┘     └──────────────────┘     └────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  PVC (20Gi)      │
                        │  HF model cache  │
                        └──────────────────┘
```

## Storage

The deployment uses a PersistentVolumeClaim for caching the HuggingFace model:

- **PVC Name**: `granite-vision-cache`
- **Size**: 20Gi
- **Purpose**: Caches the model so it doesn't re-download on pod restarts

First startup will take 5-10 minutes to download the model. Subsequent restarts use the cached model and start in ~1-2 minutes.

## Resource Requirements

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 1 | 4 |
| Memory | 12Gi | 24Gi |
| GPU | 1 | 1 |
| Storage | 20Gi PVC | - |

## Production Hardening

The base manifests include comments for production enhancements. To add:

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: granite-vision-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: granite-vision
```

### Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: granite-vision-ingress
spec:
  podSelector:
    matchLabels:
      app: granite-vision
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          app: docling-serve
    ports:
    - port: 8000
```

## Troubleshooting

### Pod Stuck in Pending

Check GPU availability:
```bash
oc get nodes -l node-role.kubernetes.io/worker-gpu -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable."nvidia\.com/gpu"
```

### Model Download Slow

First deployment downloads ~4GB. Check progress:
```bash
oc logs -f deployment/granite-vision -n granite-vision
```

### Out of Memory

Increase memory limits or reduce `--max-model-len`:
```yaml
# In overlay kustomization.yaml
patches:
- target:
    kind: Deployment
    name: granite-vision
  patch: |
    - op: replace
      path: /spec/template/spec/containers/0/resources/limits/memory
      value: 32Gi
```
