# Deploying Embedding & Reranker Models via RHOAI

This guide covers the complete workflow for deploying vLLM embedding and reranker models through Red Hat OpenShift AI (RHOAI).

## Prerequisites

1. **RHOAI installed** on your OpenShift cluster
2. **ServingRuntime templates deployed**:
   ```bash
   make deploy-rhoai-templates
   ```
3. **S3-compatible storage** (AWS S3, MinIO, Ceph, etc.)
4. **AWS CLI** configured with credentials

## Supported Models

### Embedding Models (use vLLM Embedding Runtime)

| Model | Dimensions | Max Length | Size |
|-------|------------|------------|------|
| sentence-transformers/all-MiniLM-L6-v2 | 384 | 256 | ~90MB |
| ibm-granite/granite-embedding-278m-multilingual | 768 | 512 | ~1.1GB |
| BAAI/bge-base-en-v1.5 | 768 | 512 | ~440MB |
| BAAI/bge-large-en-v1.5 | 1024 | 512 | ~1.3GB |

### Reranker Models (use vLLM Reranker Runtime)

| Model | Max Length | Size |
|-------|------------|------|
| cross-encoder/ms-marco-MiniLM-L12-v2 | 512 | ~135MB |
| BAAI/bge-reranker-base | 512 | ~1.1GB |
| BAAI/bge-reranker-large | 512 | ~1.3GB |

## Step 1: Prepare Model Files

### Option A: Using the Prepare Script

```bash
cd models/vllm-embeddings

# Download and upload embedding model
./scripts/prepare-model.sh sentence-transformers/all-MiniLM-L6-v2 your-bucket models/embeddings

# Download and upload reranker model
./scripts/prepare-model.sh cross-encoder/ms-marco-MiniLM-L12-v2 your-bucket models/rerankers
```

### Option B: Manual Steps

```bash
# 1. Install huggingface_hub
pip install huggingface_hub

# 2. Download model
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 \
  --local-dir ./all-MiniLM-L6-v2 \
  --local-dir-use-symlinks False

# 3. Upload to S3
aws s3 sync ./all-MiniLM-L6-v2 s3://your-bucket/models/all-MiniLM-L6-v2/
```

### What Files Are Uploaded?

vLLM needs the standard HuggingFace model files:

```
all-MiniLM-L6-v2/
├── config.json              # Model architecture config
├── tokenizer.json           # Tokenizer vocabulary
├── tokenizer_config.json    # Tokenizer settings
├── special_tokens_map.json  # Special tokens
├── vocab.txt                # Vocabulary (for some models)
├── model.safetensors        # Model weights (preferred)
│   └── (or pytorch_model.bin)
├── modules.json             # sentence-transformers module config
└── sentence_bert_config.json # sentence-transformers config
```

**No conversion needed** - vLLM reads HuggingFace format directly (unlike Caikit which requires conversion).

## Step 2: Create Data Connection in RHOAI

1. Go to **OpenShift AI → Data Science Projects → [Your Project]**
2. Click **Data Connections** tab
3. Click **Add data connection**
4. Fill in:
   - **Name**: `embedding-models` (or descriptive name)
   - **Access key**: Your AWS access key
   - **Secret key**: Your AWS secret key
   - **Endpoint**: S3 endpoint (e.g., `https://s3.us-east-1.amazonaws.com`)
   - **Region**: Your S3 region
   - **Bucket**: Your bucket name (e.g., `your-bucket`)

## Step 3: Deploy Model via RHOAI UI

1. Go to **OpenShift AI → Models**
2. Click **Deploy model**
3. Configure:

   **Model Settings:**
   - **Model name**: `minilm-embedding` (or descriptive name)
   - **Serving runtime**:
     - For embeddings: `vLLM Embedding Runtime`
     - For rerankers: `vLLM Reranker Runtime`

   **Model Location:**
   - **Model location type**: Existing data connection
   - **Data connection**: Select your data connection
   - **Path**: `models/all-MiniLM-L6-v2` (path within bucket)

   **Resources:**
   - **Model server size**: Small (or custom)
   - **Accelerator**: NVIDIA GPU
   - **Number of accelerators**: 1

4. Click **Deploy**

## Step 4: Verify Deployment

Once deployed, RHOAI creates:
- An InferenceService in your namespace
- A Route for external access

### Check Status

```bash
# Check InferenceService
oc get inferenceservice -n your-namespace

# Get the route URL
oc get routes -n your-namespace
```

### Test the Endpoint

**Embedding model:**
```bash
ROUTE=$(oc get route minilm-embedding -n your-namespace -o jsonpath='{.spec.host}')

curl -sk "https://$ROUTE/v1/embeddings" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "model": "minilm-embedding"}'
```

**Reranker model:**
```bash
ROUTE=$(oc get route msmarco-reranker -n your-namespace -o jsonpath='{.spec.host}')

curl -sk "https://$ROUTE/v1/score" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "msmarco-reranker",
    "text_1": "What is machine learning?",
    "text_2": "Machine learning is a subset of artificial intelligence."
  }'
```

## Troubleshooting

### Model fails to load

**Check logs:**
```bash
oc logs -l serving.kserve.io/inferenceservice=minilm-embedding -n your-namespace
```

**Common issues:**

1. **"max_model_len exceeds max_position_embeddings"**
   - The ServingRuntime needs `--max-model-len` adjusted
   - Create a custom ServingRuntime with correct value

2. **"Model not found at /mnt/models"**
   - Check data connection credentials
   - Verify S3 path is correct
   - Check bucket permissions

3. **"Permission denied" errors**
   - OpenShift runs containers as non-root
   - The ServingRuntime templates already handle this with proper env vars

### GPU not assigned

Check if GPU quota is available:
```bash
oc describe node | grep -A5 "nvidia.com/gpu"
```

### Route not created

RHOAI should create routes automatically. If not:
```bash
oc create route edge minilm-embedding \
  --service=minilm-embedding-predictor \
  --port=8080 \
  -n your-namespace
```

## Adding Model-Specific Configuration

If a model needs specific settings (like `--max-model-len`), you have two options:

### Option 1: Custom ServingRuntime (Recommended for reuse)

Create a model-specific ServingRuntime template that includes the required args.

### Option 2: Via RHOAI Model Configuration

When deploying, use the "Additional serving runtime parameters" field to pass extra args:
```
--max-model-len=256
```

## API Reference

### Embedding Endpoint

**POST /v1/embeddings**

```json
{
  "input": "Text to embed",
  "model": "model-name"
}
```

Response:
```json
{
  "data": [{"embedding": [0.1, 0.2, ...], "index": 0}],
  "model": "model-name",
  "usage": {"prompt_tokens": 4, "total_tokens": 4}
}
```

### Reranker Endpoints

**POST /v1/score** (single pair)

```json
{
  "model": "model-name",
  "text_1": "query",
  "text_2": "document"
}
```

**POST /v1/rerank** (batch, Cohere-compatible)

```json
{
  "model": "model-name",
  "query": "What is AI?",
  "documents": ["Doc 1...", "Doc 2...", "Doc 3..."],
  "top_n": 3
}
```

## Quick Reference

| Task | Command |
|------|---------|
| Deploy templates to RHOAI | `make deploy-rhoai-templates` |
| Prepare model for S3 | `./scripts/prepare-model.sh <model-id> <bucket>` |
| Check templates | `oc get templates -n redhat-ods-applications \| grep vllm` |
| Check deployments | `oc get inferenceservice -n your-namespace` |
