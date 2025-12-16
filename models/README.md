# Self-Hosted Models for OpenShift AI

This directory contains configuration, scripts, and deployment manifests for self-hosted ML models on OpenShift AI.

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

### Ministral-8B LLM (Namespace: `ministral`)

| Model | Size | Features | Route Name |
|-------|------|----------|------------|
| `mistralai/Ministral-8B-Instruct-2410` | ~15GB | Tool calling, multilingual, code generation | `ministral-8b` |

**Endpoint pattern**: `https://<route-name>-ministral.apps.<cluster-domain>`

OpenAI-compatible chat API with function/tool calling support via vLLM runtime.

See [ministral-8b/README.md](ministral-8b/README.md) for deployment guide, LibreChat integration, and MCP tool usage.

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

### Faster-Whisper Transcription (Namespace: `faster-whisper`)

| Model | Framework | Features | Service Name |
|-------|-----------|----------|--------------|
| `faster-whisper medium` | CTranslate2 | Word-level timestamps, GPU accelerated | `faster-whisper` |

**Internal endpoint**: `http://faster-whisper.faster-whisper.svc.cluster.local:8080`

Custom FastAPI service providing transcription with word-level timestamps for speaker diarization alignment. Cluster-internal only (no external route). Designed to work with pyannote-server for combined transcription and diarization workflows.

See [faster-whisper/README.md](faster-whisper/README.md) for deployment guide and API usage.

### Pyannote Speaker Diarization (Namespace: `models`)

| Model | Framework | Features | Route Name |
|-------|-----------|----------|------------|
| `pyannote/speaker-diarization-3.1` | pyannote.audio 4.x | Speaker diarization, VAD | `pyannote-server` |

**Endpoint pattern**: `https://pyannote-server-models.apps.<cluster-domain>`

Custom FastAPI server for speaker diarization ("who spoke when"). Requires GPU and HuggingFace token.

See [pyannote/README.md](pyannote/README.md) for deployment guide and API usage.

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

### Ministral-8B API (vLLM/OpenAI-compatible)

```bash
MINISTRAL_URL="https://ministral-8b-ministral.${CLUSTER_DOMAIN}"
curl -sk "${MINISTRAL_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "ministral-8b", "messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 100}'
```

### Speech-to-Text API (Whisper/vLLM)

```bash
WHISPER_URL="https://whisper-large-fp8-models.${CLUSTER_DOMAIN}"
curl -sk "${WHISPER_URL}/v1/audio/transcriptions" \
  -F file=@audio.wav \
  -F model=whisper-large-fp8 \
  -F response_format=json
```

### Transcription API (Faster-Whisper, cluster-internal)

```bash
# From within cluster or via port-forward
curl -X POST "http://faster-whisper.faster-whisper.svc.cluster.local:8080/transcribe" \
  -F "file=@audio.wav"
```

### Speaker Diarization API (Pyannote)

```bash
PYANNOTE_URL="https://pyannote-server-models.${CLUSTER_DOMAIN}"
curl -sk "${PYANNOTE_URL}/v1/diarize" \
  -F file=@audio.wav
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
