# Caikit Embeddings and Reranker Models

This directory contains deployment configuration for self-hosted embedding and reranking models on OpenShift AI using the Caikit Standalone serving runtime.

**Namespace**: `caikit-embeddings`

## Deployed Models

| Model | Type | Parameters | Dimensions | Max Tokens | Route Name |
|-------|------|------------|------------|------------|------------|
| `ibm-granite/granite-embedding-278m-multilingual` | Embedding | 278M | 768 | 512 | `granite-embedding-278m` |
| `sentence-transformers/all-MiniLM-L6-v2` | Embedding | 22.7M | 384 | 256 | `all-minilm-l6-v2` |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | Cross-Encoder | 33.4M | N/A | 512 | `ms-marco-reranker` |

**Endpoint Pattern**: `https://<route-name>-<namespace>.apps.<cluster-domain>`

To get your cluster domain:
```bash
oc get ingresses.config/cluster -o jsonpath='{.spec.domain}'
```

## Architecture

```
                                     Noobaa S3
                                   (Model Store)
                                        |
                                        v
+----------------+     +-------------------+     +------------------+
|   Workbench    |---->|   Caikit Runtime  |---->|   Inference      |
|  (Bootstrap)   |     |   (OpenShift AI)  |     |   Endpoint       |
+----------------+     +-------------------+     +------------------+
```

## Directory Structure

```
caikit-embeddings/
├── README.md                    # This file
├── Makefile                     # make deploy-minilm, deploy-granite, etc.
├── deploy-granite-embedding.sh  # Per-model deployment scripts
├── deploy-minilm-embedding.sh
├── deploy-reranker.sh
├── scripts/                     # Bootstrap and upload scripts (run in Workbench)
│   ├── bootstrap_granite_embedding.py
│   ├── bootstrap_minilm_embedding.py
│   ├── bootstrap_reranker.py
│   ├── upload_granite_to_s3.py
│   ├── upload_minilm_to_s3.py
│   └── upload_reranker_to_s3.py
└── manifests/
    ├── base/                    # Shared resources
    │   ├── data-connection-secret.yaml
    │   └── serving-runtime.yaml
    ├── granite-embedding/       # Granite embedding model
    │   ├── inference-service.yaml
    │   └── route.yaml
    ├── minilm-embedding/        # MiniLM embedding model
    │   ├── inference-service.yaml
    │   ├── service.yaml
    │   └── route.yaml
    └── reranker/                # MS-Marco reranker
        ├── inference-service.yaml
        ├── service.yaml
        └── route.yaml
```

## Storage Configuration

### Noobaa ObjectBucketClaim
- **Bucket**: Created via ObjectBucketClaim (name varies per cluster)
- **S3 Endpoint**: `https://s3-openshift-storage.apps.<cluster-domain>`
- **Secret**: `aws-connection-model-storage` (in caikit-embeddings namespace)

To get your S3 endpoint and credentials from an existing ObjectBucketClaim:
```bash
# Get the bucket name
oc get obc -n openshift-storage -o jsonpath='{.items[0].spec.bucketName}'

# Get S3 credentials from the generated secret
oc get secret <obc-name> -n openshift-storage -o jsonpath='{.data.AWS_ACCESS_KEY_ID}' | base64 -d
oc get secret <obc-name> -n openshift-storage -o jsonpath='{.data.AWS_SECRET_ACCESS_KEY}' | base64 -d
```

### S3 Model Structure

**CRITICAL**: Caikit requires models to be nested one level deep. The InferenceService `storage.path` points to a parent folder, and Caikit discovers model subdirectories within it.

```
s3://model-storage-.../
├── granite-models/                  # Granite embedding (storage.path: granite-models)
│   └── granite-embedding-278m/
│       ├── config.yml
│       └── artifacts/
│           ├── model.safetensors
│           ├── tokenizer.json
│           └── ...
├── minilm-models/                   # MiniLM embedding (storage.path: minilm-models)
│   └── all-minilm-l6-v2/
│       ├── config.yml
│       └── artifacts/
│           ├── model.safetensors
│           ├── tokenizer.json
│           └── ...
└── models/                          # Reranker (storage.path: models)
    └── ms-marco-reranker/
        ├── config.yml
        └── artifacts/
            ├── model.safetensors
            ├── tokenizer.json
            └── ...
```

**Why nested structure matters**:
- **WRONG**: `s3://bucket/granite-embedding-278m/config.yml` (flat)
- **RIGHT**: `s3://bucket/granite-models/granite-embedding-278m/config.yml` (nested)

The `storage.path` in InferenceService is the parent folder (`granite-models`), not the model folder.
Each InferenceService uses a separate parent folder to avoid loading unrelated models.

## Quick Start with Makefile

The easiest way to deploy models is using the Makefile:

```bash
# See all available targets
make help

# Deploy a single model (after S3 upload is complete)
make deploy-minilm      # all-MiniLM-L6-v2 (384 dims, lightweight)
make deploy-granite     # Granite 278M (768 dims, multilingual)
make deploy-reranker    # MS-MARCO reranker

# Deploy all models
make deploy-all

# Check status
make status

# Test endpoints
make test-minilm
make test-all
```

## Full Deployment Steps

### 1. Bootstrap Model in OpenShift AI Workbench

```bash
# Install caikit-nlp
pip install caikit-nlp boto3

# Bootstrap the model you want (choose one or more)
make bootstrap-minilm    # or: python scripts/bootstrap_minilm_embedding.py
make bootstrap-granite   # or: python scripts/bootstrap_granite_embedding.py
make bootstrap-reranker  # or: python scripts/bootstrap_reranker.py
```

Or manually:

```python
import os
from caikit_nlp.modules.text_embedding import EmbeddingModule

MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"
OUTPUT_DIR = "/opt/app-root/src/models/granite-embedding-278m"

os.makedirs(os.path.dirname(OUTPUT_DIR), exist_ok=True)

print(f"Bootstrapping {MODEL_NAME}...")
model = EmbeddingModule.bootstrap(MODEL_NAME)
model.save(OUTPUT_DIR)
print(f"Model saved to {OUTPUT_DIR}")
```

### 2. Upload to S3 with Correct Structure

After bootstrapping, upload the model to S3:

```bash
# First, set S3 credentials as environment variables
export S3_ENDPOINT='https://s3-openshift-storage.apps.your-cluster.com'
export AWS_ACCESS_KEY_ID='your-access-key'
export AWS_SECRET_ACCESS_KEY='your-secret-key'
export S3_BUCKET='your-bucket-name'

# Or copy and source from the example file
cp ../models/.env.example .env
# Edit .env with your values
source .env

# Upload the model you bootstrapped (still in Workbench)
make upload-minilm    # or: python scripts/upload_minilm_to_s3.py
make upload-granite   # or: python scripts/upload_granite_to_s3.py
make upload-reranker  # or: python scripts/upload_reranker_to_s3.py
```

**Required Environment Variables:**
| Variable | Description |
|----------|-------------|
| `S3_ENDPOINT` | S3/Noobaa endpoint URL |
| `AWS_ACCESS_KEY_ID` | S3 access key |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key |
| `S3_BUCKET` | Target bucket name |

See `models/.env.example` for a template.

### 3. Deploy the Model (from local machine with oc access)

```bash
# Option 1: Use Makefile (recommended)
make deploy-minilm      # Deploy MiniLM
make deploy-granite     # Deploy Granite
make deploy-reranker    # Deploy reranker
make deploy-all         # Deploy all models

# Option 2: Use individual scripts
./deploy-minilm-embedding.sh [namespace]
./deploy-granite-embedding.sh [namespace]
./deploy-reranker.sh [namespace]

# Option 3: Manual deployment
oc apply -f manifests/base/serving-runtime.yaml -n caikit-embeddings
oc apply -f manifests/minilm-embedding/inference-service.yaml -n caikit-embeddings
```

The deployment scripts and Makefile handle:
- Creating namespace if needed
- Deploying ServingRuntime
- Verifying data connection secret exists
- Deploying InferenceService
- Waiting for deployment readiness
- Displaying endpoint URL and test command

**Important**: The `storage.path` in the InferenceService must be the parent folder (e.g., `granite-models`), not the full model path.

### 4. Create External Route (if needed)

```bash
# For Granite embedding
oc apply -f manifests/granite-embedding/route.yaml -n caikit-embeddings

# For MiniLM embedding
oc apply -f manifests/minilm-embedding/route.yaml -n caikit-embeddings
oc apply -f manifests/minilm-embedding/service.yaml -n caikit-embeddings

# For reranker
oc apply -f manifests/reranker/route.yaml -n caikit-embeddings
oc apply -f manifests/reranker/service.yaml -n caikit-embeddings
```

## API Usage

### Embedding Endpoint (`/api/v1/task/embedding`)

```bash
# Get your endpoint URL
GRANITE_URL=$(oc get route granite-embedding-278m -n caikit-embeddings -o jsonpath='https://{.spec.host}')

curl -X POST "${GRANITE_URL}/api/v1/task/embedding" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "granite-embedding-278m", "inputs": "Your text here"}'
```

### Response Format

```json
{
  "result": {
    "data": {
      "values": [0.018, -0.039, ...]
    }
  },
  "producer_id": {
    "name": "EmbeddingModule",
    "version": "0.0.1"
  },
  "input_token_count": 4
}
```

### Python Client

```python
import os
import requests

# Set via environment or replace with your route URL
EMBEDDING_URL = os.getenv("GRANITE_EMBEDDING_URL", "https://granite-embedding-278m-caikit-embeddings.apps.<cluster-domain>")
EMBEDDING_URL += "/api/v1/task/embedding"

def get_embedding(text: str) -> list[float]:
    response = requests.post(
        EMBEDDING_URL,
        json={"model_id": "granite-embedding-278m", "inputs": text},
        verify=False  # Set to True in production with proper certs
    )
    return response.json()["result"]["data"]["values"]

# Example
embedding = get_embedding("The quick brown fox")
print(f"Embedding dimension: {len(embedding)}")  # 768
```

### MiniLM Embedding Endpoint

```bash
# Get your endpoint URL
MINILM_URL=$(oc get route all-minilm-l6-v2 -n caikit-embeddings -o jsonpath='https://{.spec.host}')

curl -X POST "${MINILM_URL}/api/v1/task/embedding" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "all-minilm-l6-v2", "inputs": "Your text here"}'
```

**Response Format**: Same as Granite embedding but with 384-dimensional vectors.

### Python MiniLM Client

```python
import os
import requests

# Set via environment or replace with your route URL
MINILM_URL = os.getenv("MINILM_EMBEDDING_URL", "https://all-minilm-l6-v2-caikit-embeddings.apps.<cluster-domain>")
MINILM_URL += "/api/v1/task/embedding"

def get_minilm_embedding(text: str) -> list[float]:
    response = requests.post(
        MINILM_URL,
        json={"model_id": "all-minilm-l6-v2", "inputs": text},
        verify=False  # Set to True in production with proper certs
    )
    return response.json()["result"]["data"]["values"]

# Example
embedding = get_minilm_embedding("The quick brown fox")
print(f"Embedding dimension: {len(embedding)}")  # 384
```

### Reranker Endpoint (`/api/v1/task/rerank`)

```bash
# Get your endpoint URL
RERANKER_URL=$(oc get route ms-marco-reranker -n caikit-embeddings -o jsonpath='https://{.spec.host}')

curl -X POST "${RERANKER_URL}/api/v1/task/rerank" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "ms-marco-reranker",
    "inputs": {
      "query": "What is machine learning?",
      "documents": [
        {"text": "Machine learning is a branch of AI."},
        {"text": "The weather is sunny."},
        {"text": "Deep learning uses neural networks."}
      ]
    },
    "parameters": {
      "top_n": 3,
      "return_documents": true,
      "return_text": true
    }
  }'
```

### Reranker Response Format

```json
{
  "result": {
    "query": "What is machine learning?",
    "scores": [
      {
        "document": {"text": "Machine learning is a branch of AI."},
        "index": 0,
        "score": 5.65,
        "text": "Machine learning is a branch of AI."
      },
      {
        "document": {"text": "Deep learning uses neural networks."},
        "index": 2,
        "score": -5.17,
        "text": "Deep learning uses neural networks."
      },
      {
        "document": {"text": "The weather is sunny."},
        "index": 1,
        "score": -11.10,
        "text": "The weather is sunny."
      }
    ]
  },
  "producer_id": {
    "name": "CrossEncoderModule",
    "version": "0.0.1"
  },
  "input_token_count": 39
}
```

### Python Reranker Client

```python
import os
import requests

# Set via environment or replace with your route URL
RERANK_URL = os.getenv("RERANKER_URL", "https://ms-marco-reranker-caikit-embeddings.apps.<cluster-domain>")
RERANK_URL += "/api/v1/task/rerank"

def rerank_documents(query: str, documents: list[str], top_n: int = None) -> list[dict]:
    """Rerank documents by relevance to query. Returns sorted by score (highest first)."""
    payload = {
        "model_id": "ms-marco-reranker",
        "inputs": {
            "query": query,
            "documents": [{"text": doc} for doc in documents]
        },
        "parameters": {
            "return_documents": True,
            "return_text": True
        }
    }
    if top_n:
        payload["parameters"]["top_n"] = top_n

    response = requests.post(RERANK_URL, json=payload, verify=False)  # Set verify=True in production
    return response.json()["result"]["scores"]

# Example
docs = [
    "Machine learning enables computers to learn from data.",
    "The capital of France is Paris.",
    "Neural networks are inspired by biological neurons."
]
results = rerank_documents("What is machine learning?", docs, top_n=2)
for r in results:
    print(f"Score: {r['score']:.2f} - {r['text']}")
```

## Troubleshooting

### Model Not Loading

If you see errors like `FileNotFoundError: Module load path does not contain a config.yml file`:

1. Check S3 structure - model must be nested: `s3://bucket/models/model-name/config.yml`
2. InferenceService `storage.path` should be the parent folder (`models`), not the full path

### Storage Path Mismatch ("No model found")

If you see `RuntimeError: Failed to fetch model. No model found in <path>`:

1. Check the InferenceService `storage.path` matches where you uploaded the model
2. Verify the S3 structure:

```bash
# List your bucket contents to see actual paths
oc exec -n minio-storage deploy/minio -- mc ls -r myminio/model-storage/
```

3. The manifest path should be the PARENT folder, not the model folder:
   - Upload to: `s3://bucket/granite-models/granite-embedding-278m/`
   - Manifest: `storage.path: granite-models`

### No S3/ODF Storage Available

If your cluster doesn't have ODF (Noobaa) installed, you can deploy minio for model storage:

```bash
# Check if minio is already available
oc get svc -A | grep minio

# If not, deploy minio (see your cluster administrator)
# Then create a data connection secret:
oc create secret generic aws-connection-model-storage \
  --from-literal=AWS_ACCESS_KEY_ID=<access-key> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<secret-key> \
  --from-literal=AWS_S3_ENDPOINT=<minio-endpoint> \
  --from-literal=AWS_S3_BUCKET=<bucket-name> \
  --from-literal=AWS_DEFAULT_REGION=us-east-1 \
  -n caikit-embeddings
```

### Pod Stuck in Init

Check storage initializer logs:

```bash
oc logs <pod-name> -c storage-initializer -n caikit-embeddings
```

Common issues:
- SSL certificate errors: Check `AWS_S3_ENDPOINT` uses correct protocol
- Access denied: Verify credentials in the data connection secret
- Bucket not found: Ensure the bucket exists and is accessible

### Version Mismatch Warning

If you see sentence_transformers version warnings, this is informational. The model will still work correctly.

## References

- [How to Serve Embeddings Models on OpenShift AI](https://developers.redhat.com/articles/2024/09/25/how-serve-embeddings-models-openshift-ai)
- [Caikit NLP Documentation](https://github.com/caikit/caikit-nlp)
- [Granite Embedding Model](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual)
- [all-MiniLM-L6-v2 Embedding Model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [MS MARCO MiniLM L12 Cross-Encoder](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L12-v2)
