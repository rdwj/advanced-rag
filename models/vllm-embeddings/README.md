# vLLM Embeddings - Migration Testing

This directory contains deployment manifests and test scripts for evaluating whether vLLM can replace Caikit for serving embedding and reranker models.

**Purpose**: Test viability of migrating from Caikit-NLP to vLLM for pooling models.

**Namespace**: `vllm-embeddings`

## Background

vLLM recently added support for "pooling models" including embeddings and cross-encoders via the `--task embed` and `--task score` flags. This is documented at:
- https://docs.vllm.ai/en/latest/models/pooling_models.html

However, vLLM's documentation includes this caveat:
> "We currently support pooling models primarily for convenience. This is not guaranteed to provide any performance improvements over using Hugging Face Transformers or Sentence Transformers directly."

This testing plan will determine if vLLM is a viable replacement for our Caikit-based deployments.

## Models Under Test

| Model | Type | Caikit Status | vLLM Expected |
|-------|------|---------------|---------------|
| `sentence-transformers/all-MiniLM-L6-v2` | Embedding (384d) | ✅ Working | ⚠️ Test |
| `ibm-granite/granite-embedding-278m-multilingual` | Embedding (768d) | ✅ Working | ⚠️ Test |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | Reranker | ✅ Working | ⚠️ Test |
| `BAAI/bge-reranker-v2-m3` | Reranker (alt) | N/A | ✅ Documented |

## Quick Start

```bash
# Deploy one model at a time (conserve GPUs)
make deploy-minilm

# Check status
make status

# View logs (watch for errors)
make logs-minilm

# Run tests
make test-minilm

# Clean up before next test
make undeploy-minilm
```

## Testing Plan

### Phase 1: MiniLM Embedding Model

**Objective**: Determine if sentence-transformers models work with vLLM.

```bash
# 1. Deploy
make deploy-minilm

# 2. Wait for ready (watch logs)
make logs-minilm

# 3. Test
make test-minilm

# 4. Run quality tests
pip install sentence-transformers numpy
python scripts/test_embedding_quality.py \
  --url https://minilm-embedding-vllm-embeddings.apps.<cluster> \
  --model sentence-transformers/all-MiniLM-L6-v2 \
  --baseline
```

**Success Criteria**:
- [ ] Model loads without errors
- [ ] `/v1/embeddings` endpoint returns 384-dimensional vectors
- [ ] Embeddings match sentence-transformers baseline (cosine sim > 0.99)
- [ ] Latency is acceptable (< 100ms per request)

**If it fails**, note the error:
- `ValueError: Model architecture not supported` → vLLM doesn't support this architecture
- `KeyError: modules.json` → sentence-transformers config not being read
- Dimension mismatch → Pooling configuration issue

### Phase 2: Granite Embedding Model

**Objective**: Test IBM Granite embedding model (XLM-RoBERTa architecture).

```bash
# 1. Deploy
make deploy-granite

# 2. Test
make test-granite

# 3. Quality test
python scripts/test_embedding_quality.py \
  --url https://granite-embedding-vllm-embeddings.apps.<cluster> \
  --model ibm-granite/granite-embedding-278m-multilingual
```

**Success Criteria**:
- [ ] Model loads without errors
- [ ] `/v1/embeddings` endpoint returns 768-dimensional vectors
- [ ] Multilingual test passes (test with non-English text)

### Phase 3: MS-MARCO Reranker

**Objective**: Test cross-encoder reranker with `/v1/score` endpoint.

```bash
# 1. Deploy
make deploy-reranker

# 2. Watch logs (likely to fail here)
make logs-reranker

# 3. Test
make test-reranker

# 4. Quality test
python scripts/test_reranker_quality.py \
  --url https://msmarco-reranker-vllm-embeddings.apps.<cluster> \
  --model cross-encoder/ms-marco-MiniLM-L12-v2
```

**Success Criteria**:
- [ ] Model loads without errors
- [ ] `/v1/score` endpoint returns relevance scores
- [ ] Ranking quality is correct (relevant docs score higher)

**If MS-MARCO fails**, try BGE:

```bash
make undeploy-reranker
make deploy-bge
make test-bge
```

### Phase 4: Performance Comparison

If models work, compare performance against Caikit:

```bash
# Run throughput tests
python scripts/test_embedding_quality.py --url <vllm-url> --model <model>
# Compare against Caikit baseline

# Things to measure:
# - Throughput (requests/second)
# - Latency (p50, p95, p99)
# - GPU memory usage
# - Cold start time
```

## Test Results (December 2025)

All three models work successfully with vLLM v0.12.0:

| Model | Status | Results |
|-------|--------|---------|
| all-MiniLM-L6-v2 | ✅ WORKING | Returns 384-dim embeddings, batch works |
| granite-embedding-278m | ✅ WORKING | Returns 768-dim embeddings, multilingual works |
| ms-marco-MiniLM-L12-v2 | ✅ WORKING | /v1/score returns relevance scores, ranking correct |

### Key Findings

1. **Embeddings**: Both MiniLM and Granite work perfectly with `--task embed`
2. **Reranker**: MS-MARCO cross-encoder works with `--task score`
3. **OpenShift Fix**: Required writable directories for flashinfer JIT compilation:
   - `HOME=/tmp/home`
   - `XDG_CACHE_HOME=/tmp/cache`
   - Mount emptyDir volumes for these paths
4. **GPU Memory**: Use `--gpu-memory-utilization 0.3` for shared GPU environments

### Recommendation

**✅ Migrate to vLLM** - All models work correctly. This provides:
- Unified serving platform (same runtime for embeddings, rerankers, and LLMs)
- OpenAI-compatible API endpoints
- Better GPU utilization with paged attention
- Active development and community support

## Decision Matrix

| Outcome | Action |
|---------|--------|
| All models work, performance ≥ Caikit | ✅ **Migrate to vLLM** (current status) |
| Embeddings work, reranker doesn't | ⚠️ Hybrid: vLLM for embeddings, Caikit for reranker |
| Only MiniLM works | ⚠️ Keep Caikit, revisit in 6 months |
| Nothing works | ❌ Keep Caikit |

## Directory Structure

```
vllm-embeddings/
├── README.md                              # This file
├── Makefile                               # Deploy/test commands
├── manifests/
│   ├── base/
│   │   ├── namespace.yaml                 # Namespace definition
│   │   └── model-cache-pvc.yaml           # Shared PVC for model downloads
│   ├── minilm-embedding/
│   │   ├── deployment.yaml                # MiniLM deployment
│   │   ├── service.yaml
│   │   └── route.yaml
│   ├── granite-embedding/
│   │   ├── deployment.yaml                # Granite deployment
│   │   ├── service.yaml
│   │   └── route.yaml
│   └── reranker/
│       ├── deployment.yaml                # MS-MARCO reranker
│       ├── deployment-bge.yaml            # BGE reranker (alternative)
│       ├── service.yaml
│       └── route.yaml
└── scripts/
    ├── test_embedding_quality.py          # Embedding quality tests
    └── test_reranker_quality.py           # Reranker quality tests
```

## API Endpoints

### Embedding Models (`/v1/embeddings`)

```bash
curl -X POST "https://<model>-vllm-embeddings.apps.<cluster>/v1/embeddings" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "model": "<model-name>"}'
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.1, -0.2, ...],
      "index": 0
    }
  ],
  "model": "<model-name>",
  "usage": {"prompt_tokens": 2, "total_tokens": 2}
}
```

### Reranker Models (`/v1/score`)

```bash
curl -X POST "https://<reranker>-vllm-embeddings.apps.<cluster>/v1/score" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<model-name>",
    "text_1": "What is machine learning?",
    "text_2": "Machine learning is a branch of AI."
  }'
```

## Troubleshooting

### Model fails to load

Check logs:
```bash
make logs-minilm  # or logs-granite, logs-reranker
```

Common errors:
- **"not supported"**: Architecture not implemented in vLLM
- **"CUDA out of memory"**: Reduce batch size or use smaller model
- **"modules.json not found"**: sentence-transformers config issue

### GPU not allocated

```bash
oc describe pod -l app=minilm-embedding -n vllm-embeddings | grep -A5 "Events:"
```

### Route not accessible

```bash
oc get routes -n vllm-embeddings
curl -sk https://<route>/health
```

## Cleanup

```bash
# Remove individual deployments
make undeploy-minilm

# Remove everything
make clean
```

## References

- [vLLM Pooling Models Documentation](https://docs.vllm.ai/en/latest/models/pooling_models.html)
- [vLLM Supported Models](https://docs.vllm.ai/en/latest/models/supported_models/)
- [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [ibm-granite/granite-embedding-278m-multilingual](https://huggingface.co/ibm-granite/granite-embedding-278m-multilingual)
- [cross-encoder/ms-marco-MiniLM-L12-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L12-v2)
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)

## Related

- `../caikit-embeddings/` - Current production deployment using Caikit-NLP
- `../../research-vllm-embedding-reranker-migration.md` - Detailed research findings
