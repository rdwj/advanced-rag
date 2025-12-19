# vLLM Embedding/Reranker Migration - Lessons Learned

This document captures key findings from testing vLLM for serving embedding and reranker models on OpenShift.

## Deployment Approach

**Current**: Raw Kubernetes Deployments in namespace `vllm-embeddings`

**Note**: These deployments do NOT use KServe InferenceService or OpenShift AI ServingRuntime. They are standalone Deployments with Services and Routes. This means:
- Models won't appear in OpenShift AI's model serving dashboard
- No automatic scaling, canary deployments, or model versioning from KServe
- Simpler setup but less enterprise features

**Future consideration**: Create a KServe-compatible ServingRuntime for vLLM pooling models if OpenShift AI integration is needed.

## Key Lessons

### 1. max-model-len Must Match Model's Actual Limit

**Problem**: Setting `--max-model-len 512` when the model only supports 256 causes startup failure.

**Error**:
```
ValueError: max_model_len (512) is greater than the derived max_model_len
(max_position_embeddings=256 in model config)
```

**Solution**: Check the model's `config.json` on HuggingFace for `max_position_embeddings` and set `--max-model-len` to that value or lower.

| Model | max_position_embeddings |
|-------|------------------------|
| all-MiniLM-L6-v2 | 256 |
| granite-embedding-278m-multilingual | 512 |
| ms-marco-MiniLM-L12-v2 | 512 |

### 2. OpenShift Rootless Containers Need Writable Cache Directories

**Problem**: vLLM uses flashinfer for JIT compilation, which tries to write to `/.cache`. OpenShift runs containers as non-root with read-only root filesystem.

**Error**:
```
PermissionError: [Errno 13] Permission denied: '/.cache'
```

**Solution**: Set environment variables and mount writable volumes:

```yaml
env:
  - name: HOME
    value: /tmp/home
  - name: XDG_CACHE_HOME
    value: /tmp/cache
  - name: VLLM_CACHE_DIR
    value: /models/vllm-cache
volumeMounts:
  - name: tmp-cache
    mountPath: /tmp/cache
  - name: tmp-home
    mountPath: /tmp/home
volumes:
  - name: tmp-cache
    emptyDir: {}
  - name: tmp-home
    emptyDir: {}
```

### 3. GPU Memory Utilization for Shared Environments

**Problem**: Default GPU memory utilization (0.9) fails when other workloads are using the same GPU.

**Error**:
```
ValueError: Free memory on device (7.39/21.98 GiB) is less than
desired GPU memory utilization (0.9, 19.78 GiB)
```

**Solution**: Set `--gpu-memory-utilization` to a lower value:

```yaml
args:
  - --gpu-memory-utilization
  - "0.3"  # Use 30% of GPU memory
```

For embedding models, 0.3 is usually sufficient since they're much smaller than LLMs.

### 4. vLLM API Deprecation Warnings

**Current warnings** (vLLM v0.12.0):
- `--model` flag is deprecated; use positional argument or config file
- `task` argument is deprecated

These are warnings only and don't affect functionality in v0.12.0, but may break in v0.13+.

### 5. Shared PVC for Model Caching

**Approach**: Use a single PVC (`vllm-model-cache`) shared by all deployments.

**Benefit**: Models are downloaded once and cached. Subsequent deployments start faster.

**Consideration**: Only one deployment can run at a time if they're competing for GPU resources, but they can share the cached model files.

### 6. Health Probe Timing

**Observation**: Embedding models typically load in 60-90 seconds. Set probes accordingly:

```yaml
livenessProbe:
  initialDelaySeconds: 180  # Allow time for model download on first run
  periodSeconds: 30
readinessProbe:
  initialDelaySeconds: 90   # Model should be loaded by then
  periodSeconds: 10
```

### 7. vLLM Pooling Model API Endpoints

**Embeddings** (`--task embed`):
- `POST /v1/embeddings` - OpenAI-compatible
- Request: `{"input": "text", "model": "model-name"}`
- Response: `{"data": [{"embedding": [...], "index": 0}]}`

**Rerankers** (`--task score`):
- `POST /v1/score` - vLLM-specific
- Request: `{"model": "model-name", "text_1": "query", "text_2": "document"}`
- Response: `{"data": [{"score": 10.45}]}`

Also available:
- `POST /v1/rerank` - Cohere-compatible batch reranking
- `POST /v2/rerank` - Alternative rerank endpoint

## Tested Models

| Model | Type | Task Flag | Dimension/Output | Status |
|-------|------|-----------|------------------|--------|
| sentence-transformers/all-MiniLM-L6-v2 | Embedding | embed | 384-dim vectors | ✅ Works |
| ibm-granite/granite-embedding-278m-multilingual | Embedding | embed | 768-dim vectors | ✅ Works |
| cross-encoder/ms-marco-MiniLM-L12-v2 | Reranker | score | Relevance scores | ✅ Works |

## Resource Requirements

Tested on NVIDIA GPUs in OpenShift:

| Model | GPU Memory | CPU | RAM |
|-------|-----------|-----|-----|
| all-MiniLM-L6-v2 | ~1GB | 2 cores | 4Gi |
| granite-embedding-278m | ~2GB | 2 cores | 8Gi |
| ms-marco-MiniLM-L12-v2 | ~1GB | 2 cores | 4Gi |

## Migration Recommendation

**Verdict**: ✅ Migrate from Caikit to vLLM

**Reasons**:
1. All tested models work correctly
2. Unified runtime for embeddings, rerankers, and LLMs
3. OpenAI-compatible API simplifies client integration
4. Active development and community support
5. Better GPU memory management with paged attention

**Next steps**:
1. Performance benchmarking against Caikit
2. ~~Consider creating KServe ServingRuntime for OpenShift AI integration~~ ✅ Done
3. Update downstream services to use new endpoints

---

## KServe Integration (OpenShift AI Model Deployments)

Successfully integrated vLLM pooling models with KServe for OpenShift AI dashboard visibility.

### Architecture: Two ServingRuntimes

vLLM requires different `--task` flags for embeddings vs rerankers, so we created two separate ServingRuntimes:

1. **`vllm-embedding-runtime`** - For embedding models (`--task embed`)
2. **`vllm-reranker-runtime`** - For reranker/cross-encoder models (`--task score`)

### Key KServe Lessons

#### 1. Use `python3` Not `python` in vLLM Container

**Problem**: KServe ServingRuntime with `command: [python]` fails.

**Error**:
```
executable file `python` not found in $PATH
```

**Solution**: Use `python3` in the ServingRuntime container command:
```yaml
command:
  - python3
  - -m
  - vllm.entrypoints.openai.api_server
```

#### 2. RawDeployment Mode Requires Manual Routes

**Problem**: KServe with `serving.kserve.io/deploymentMode: RawDeployment` doesn't create OpenShift Routes automatically.

**Solution**: Create routes manually pointing to the `-metrics` service:
```bash
oc create route edge minilm-embedding --service=minilm-embedding-metrics --port=8080
```

The KServe-managed services:
- `<name>-predictor` - Headless service (ClusterIP: None)
- `<name>-metrics` - ClusterIP service on port 8080 (use this for routes)

#### 3. Required Labels and Annotations for OpenShift AI

**ServingRuntime**:
```yaml
metadata:
  labels:
    opendatahub.io/dashboard: "true"
  annotations:
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
    openshift.io/display-name: vLLM Embedding Runtime
```

**InferenceService**:
```yaml
metadata:
  labels:
    opendatahub.io/dashboard: "true"
  annotations:
    openshift.io/display-name: MiniLM Embedding (vLLM)
    serving.kserve.io/deploymentMode: RawDeployment
```

#### 4. Model Args via InferenceService

ServingRuntime defines the base args (`--task`, `--dtype`, etc.).
InferenceService adds model-specific args:

```yaml
# InferenceService
spec:
  predictor:
    model:
      args:
        - --model=sentence-transformers/all-MiniLM-L6-v2
        - --max-model-len=256
```

These args are appended to the ServingRuntime's container args.

#### 5. Shared PVC for Model Storage

Mount existing `vllm-model-cache` PVC in ServingRuntime:
```yaml
volumes:
  - name: model-cache
    persistentVolumeClaim:
      claimName: vllm-model-cache
env:
  - name: HF_HOME
    value: /models/huggingface
```

This allows KServe InferenceServices to reuse cached models from raw deployments.

### KServe Deployment Commands

```bash
# Deploy ServingRuntimes
make deploy-kserve-runtimes

# Deploy individual InferenceServices
make deploy-kserve-minilm
make deploy-kserve-granite
make deploy-kserve-reranker

# Check status
make status-kserve

# Cleanup
make undeploy-kserve-all
```

### Critical: Templates vs Direct ServingRuntimes for RHOAI

**Problem**: Applying a `ServingRuntime` YAML directly works in OpenShift but **does NOT appear in RHOAI dashboard**.

**Solution**: Deploy ServingRuntimes as OpenShift **Templates** to the `redhat-ods-applications` namespace.

**Key differences**:

| Approach | Namespace | RHOAI Visible | Selectable for New Models |
|----------|-----------|---------------|---------------------------|
| Direct ServingRuntime | Project namespace | ❌ No | ❌ No |
| Template | redhat-ods-applications | ✅ Yes | ✅ Yes |

**Template structure**:
```yaml
apiVersion: template.openshift.io/v1
kind: Template
metadata:
  annotations:
    opendatahub.io/apiProtocol: REST
    opendatahub.io/model-type: '["embedding"]'  # or ["reranker"], ["generative"]
    opendatahub.io/modelServingSupport: '["single"]'
    openshift.io/display-name: vLLM Embedding Runtime for KServe
  labels:
    opendatahub.io/dashboard: "true"
  name: vllm-embedding-runtime
  namespace: redhat-ods-applications  # MUST be this namespace
objects:
- apiVersion: serving.kserve.io/v1alpha1
  kind: ServingRuntime
  # ... ServingRuntime spec wrapped in objects array
```

**Deployment**:
```bash
make deploy-rhoai-templates  # Deploys to redhat-ods-applications
```

### RHOAI Model Deployment Flow

When using RHOAI's model deployment UI:
1. Model data comes from a **Data Connection** (S3, PVC, etc.)
2. Model files are mounted at `/mnt/models`
3. ServingRuntime uses `--model=/mnt/models`
4. Model name set via `--served-model-name={{.Name}}`

This is different from direct HuggingFace download approach used in raw deployments.

### Verified Working

| Resource | Location | Status |
|----------|----------|--------|
| vLLM Embedding Runtime Template | redhat-ods-applications | ✅ Visible in RHOAI |
| vLLM Reranker Runtime Template | redhat-ods-applications | ✅ Visible in RHOAI |

Templates now appear in **OpenShift AI → Settings → Serving Runtimes** and can be selected when deploying new models.

### Model Preparation: vLLM vs Caikit

**Key difference**: vLLM reads HuggingFace format directly - **no conversion step needed**.

| Step | Caikit | vLLM |
|------|--------|------|
| Download from HuggingFace | Required | Required |
| Convert to framework format | Required (caikit-nlp) | **Not needed** |
| Upload to S3 | Required | Required |

**Workflow**:
```bash
# Use the prepare script
./scripts/prepare-model.sh sentence-transformers/all-MiniLM-L6-v2 my-bucket models

# Or manually:
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir ./model
aws s3 sync ./model s3://my-bucket/models/all-MiniLM-L6-v2/
```

See `docs/RHOAI_DEPLOYMENT.md` for the complete deployment guide.
