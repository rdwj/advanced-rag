# Self-Hosted Models for OpenShift AI

This directory contains configuration, scripts, and deployment manifests for self-hosted ML models on OpenShift AI.

## Directory Structure

```
models/
├── caikit-embeddings/          # Embedding and reranker models (Caikit runtime)
│   ├── README.md               # Detailed documentation
│   ├── Makefile                # Deploy targets (make deploy-all, etc.)
│   ├── scripts/                # Bootstrap and upload scripts
│   │   ├── bootstrap_granite_embedding.py
│   │   ├── bootstrap_minilm_embedding.py
│   │   ├── bootstrap_reranker.py
│   │   ├── upload_granite_to_s3.py
│   │   ├── upload_minilm_to_s3.py
│   │   └── upload_reranker_to_s3.py
│   └── manifests/              # OpenShift manifests
│       ├── base/               # Shared resources (runtime, secrets)
│       ├── granite-embedding/  # Granite embedding model
│       ├── minilm-embedding/   # MiniLM embedding model
│       └── reranker/           # MS-Marco reranker model
├── gpt-oss/                    # GPT-OSS LLM model (vLLM runtime)
│   ├── README.md               # Detailed documentation
│   ├── scripts/                # Download and upload scripts
│   ├── manifests/              # OpenShift manifests
│   └── tiktoken/               # Tokenizer vocabulary files
├── granite-vision/             # Granite Vision Language Model (vLLM runtime)
│   ├── README.md               # Detailed documentation
│   └── manifests/              # Kustomize base + overlays
│       ├── base/               # Core deployment resources
│       └── overlays/default/   # Default namespace overlay
└── whisper/                    # Whisper Speech-to-Text model (vLLM runtime)
    ├── README.md               # Detailed documentation
    ├── deploy.sh               # Deployment script
    ├── Makefile                # Make targets
    └── manifests/              # OpenShift manifests
        ├── namespace.yaml
        ├── serving-runtime.yaml
        └── inference-service.yaml
```

## Deployed Models

### Caikit Embeddings (Namespace: `caikit-embeddings`)

| Model | Type | Dimensions | Route Name |
|-------|------|------------|------------|
| `ibm-granite/granite-embedding-278m-multilingual` | Embedding | 768 | `granite-embedding-278m` |
| `sentence-transformers/all-MiniLM-L6-v2` | Embedding | 384 | `all-minilm-l6-v2` |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | Reranker | N/A | `ms-marco-reranker` |

**Endpoint pattern**: `https://<route-name>-caikit-embeddings.apps.<cluster-domain>`

See [caikit-embeddings/README.md](caikit-embeddings/README.md) for deployment, API usage, and troubleshooting.

### GPT-OSS LLM (Namespace: `gpt-oss`)

| Model | Size | Features | Route Name |
|-------|------|----------|------------|
| `RedHatAI/gpt-oss-20b` | 38.5GB | Tool calling, OpenAI-compatible API | `gpt-oss-20b-rhaiis` |

**Endpoint pattern**: `https://<route-name>-gpt-oss.apps.<cluster-domain>`

See [gpt-oss/README.md](gpt-oss/README.md) for deployment guide, API usage, and LibreChat integration.

### Granite Vision (Namespace: `granite-vision`)

| Model | Parameters | Context | Route Name |
|-------|------------|---------|------------|
| `ibm-granite/granite-vision-3.2-2b` | 2B | 65,536 tokens | `granite-vision` |

**Endpoint pattern**: `https://<route-name>-granite-vision.apps.<cluster-domain>`

Used by docling-serve for generating descriptions of images within documents during PDF conversion.

See [granite-vision/README.md](granite-vision/README.md) for deployment guide and docling integration.

### Whisper Speech-to-Text (Namespace: `models`)

| Model | Quantization | Languages | Route Name |
|-------|-------------|-----------|------------|
| `RedHatAI/whisper-large-v3-turbo-FP8-dynamic` | FP8 | 99+ | `whisper-large-fp8` |

**Endpoint pattern**: `https://<route-name>-models.apps.<cluster-domain>`

OpenAI-compatible audio transcription API using RHAIIS vLLM 3.2.4+ runtime.

See [whisper/README.md](whisper/README.md) for deployment guide and API usage.

## Quick Reference

Get your cluster domain first:
```bash
CLUSTER_DOMAIN=$(oc get ingresses.config/cluster -o jsonpath='{.spec.domain}')
```

### Embedding API (Caikit)

```bash
EMBEDDING_URL="https://granite-embedding-278m-caikit-embeddings.${CLUSTER_DOMAIN}"
curl -X POST "${EMBEDDING_URL}/api/v1/task/embedding" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "granite-embedding-278m", "inputs": "Your text here"}'
```

### Reranker API (Caikit)

```bash
RERANKER_URL="https://ms-marco-reranker-caikit-embeddings.${CLUSTER_DOMAIN}"
curl -X POST "${RERANKER_URL}/api/v1/task/rerank" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "ms-marco-reranker",
    "inputs": {
      "query": "What is machine learning?",
      "documents": [{"text": "ML is a branch of AI."}]
    }
  }'
```

### LLM API (vLLM/OpenAI-compatible)

```bash
TOKEN=$(oc whoami -t)
LLM_URL="https://gpt-oss-20b-rhaiis-gpt-oss.${CLUSTER_DOMAIN}"
curl -sk "${LLM_URL}/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss-20b-rhaiis", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Speech-to-Text API (Whisper/vLLM)

```bash
WHISPER_URL="https://whisper-large-fp8-models.${CLUSTER_DOMAIN}"
curl -sk "${WHISPER_URL}/v1/audio/transcriptions" \
  -F file=@audio.wav \
  -F model=whisper-large-fp8 \
  -F response_format=json
```

## Storage

Models require S3-compatible storage for Caikit runtime. Options include:

### OpenShift Data Foundation (ODF/Noobaa)
If your cluster has ODF installed:
```bash
# Endpoint pattern
https://s3-openshift-storage.apps.<cluster-domain>
```

### MinIO (Alternative)
For clusters without ODF, deploy MinIO:
```bash
# See databases/minio/ for deployment manifests
# Endpoint pattern (internal)
http://minio.minio-storage.svc.cluster.local:9000
```

### Storage Secret
Models reference storage via a DataConnection secret named `aws-connection-model-storage` in the `caikit-embeddings` namespace. See [caikit-embeddings/README.md](caikit-embeddings/README.md) for setup instructions.

## References

- [Serving Embeddings on OpenShift AI](https://developers.redhat.com/articles/2024/09/25/how-serve-embeddings-models-openshift-ai)
- [Caikit NLP Documentation](https://github.com/caikit/caikit-nlp)
- [vLLM Documentation](https://docs.vllm.ai/)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
