# Self-Hosted Models for OpenShift AI

This directory contains configuration, scripts, and deployment manifests for self-hosted ML models on OpenShift AI.

## Directory Structure

```
models/
├── caikit-embeddings/          # Embedding and reranker models (Caikit runtime)
│   ├── README.md               # Detailed documentation
│   ├── scripts/                # Bootstrap and upload scripts
│   │   ├── bootstrap_embedding_model.py
│   │   ├── bootstrap_reranker_model.py
│   │   └── upload_reranker_to_s3.py
│   └── manifests/              # OpenShift manifests
│       ├── base/               # Shared resources (runtime, secrets)
│       ├── granite-embedding/  # Granite embedding model
│       ├── minilm-embedding/   # MiniLM embedding model
│       └── reranker/           # MS-Marco reranker model
└── gpt-oss/                    # GPT-OSS LLM model (vLLM runtime)
    ├── README.md               # Detailed documentation
    ├── scripts/                # Download and upload scripts
    ├── manifests/              # OpenShift manifests
    └── tiktoken/               # Tokenizer vocabulary files
```

## Deployed Models

### Caikit Embeddings (Namespace: `caikit-embeddings`)

| Model | Type | Dimensions | Endpoint |
|-------|------|------------|----------|
| `ibm-granite/granite-embedding-278m-multilingual` | Embedding | 768 | [Granite Embedding](https://granite-embedding-caikit-embeddings.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com) |
| `sentence-transformers/all-MiniLM-L6-v2` | Embedding | 384 | [MiniLM](https://all-minilm-l6-v2-caikit-embeddings.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com) |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | Reranker | N/A | [MS-Marco Reranker](https://ms-marco-reranker-caikit-embeddings.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com) |

See [caikit-embeddings/README.md](caikit-embeddings/README.md) for API usage, deployment steps, and troubleshooting.

### GPT-OSS LLM (Namespace: `gpt-oss`)

| Model | Size | Features | Endpoint |
|-------|------|----------|----------|
| `RedHatAI/gpt-oss-20b` | 38.5GB | Tool calling, OpenAI-compatible API | [GPT-OSS](https://gpt-oss-20b-rhaiis-gpt-oss.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com) |

See [gpt-oss/README.md](gpt-oss/README.md) for deployment guide, API usage, and LibreChat integration.

## Quick Reference

### Embedding API (Caikit)

```bash
curl -X POST "https://granite-embedding-caikit-embeddings.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com/api/v1/task/embedding" \
  -H "Content-Type: application/json" \
  -d '{"model_id": "granite-embedding", "inputs": "Your text here"}'
```

### Reranker API (Caikit)

```bash
curl -X POST "https://ms-marco-reranker-caikit-embeddings.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com/api/v1/task/rerank" \
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
curl -sk "https://gpt-oss-20b-rhaiis-gpt-oss.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss-20b-rhaiis", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Storage

All models are stored in Noobaa S3:
- **Endpoint**: `https://s3-openshift-storage.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com`
- **Bucket**: `model-storage-fd83a868-2120-4822-90af-e998f8203992`

## References

- [Serving Embeddings on OpenShift AI](https://developers.redhat.com/articles/2024/09/25/how-serve-embeddings-models-openshift-ai)
- [Caikit NLP Documentation](https://github.com/caikit/caikit-nlp)
- [vLLM Documentation](https://docs.vllm.ai/)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
