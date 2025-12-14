# Whisper Speech-to-Text Deployment Guide for OpenShift AI

This guide covers deploying the RedHatAI/whisper-large-v3-turbo-FP8-dynamic model on OpenShift AI using the RHAIIS vLLM CUDA runtime with OCI model storage.

## Prerequisites

- OpenShift cluster with OpenShift AI 2.19+ installed
- GPU node(s) with NVIDIA GPU Operator configured (CUDA 12.4+)
- Access to `registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.2.4` images
- Model published to OCI registry (e.g., `quay.io/wjackson/models:redhatai-whisper-large-v3-turbo-FP8-dynamic`)

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      OpenShift AI                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  KServe InferenceService                                 ││
│  │  ┌─────────────────────┐  ┌─────────────────────┐       ││
│  │  │   modelcar-init     │  │   kserve-container  │       ││
│  │  │   (init container)  │──│   (vLLM + model)    │       ││
│  │  │   OCI image pull    │  │   Serves API        │       ││
│  │  └──────────┬──────────┘  └──────────┬──────────┘       ││
│  │             │ /mnt/models            │ :8080            ││
│  └─────────────│────────────────────────│──────────────────┘│
│                │                        │                   │
│  ┌─────────────▼────────────────────────▼──────────────────┐│
│  │              ServingRuntime                              ││
│  │  - RHAIIS vLLM CUDA 3.2.4 (vLLM 0.11.0+rhai5)           ││
│  │  - Whisper architecture support                          ││
│  │  - OpenAI-compatible /v1/audio/transcriptions            ││
│  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
         │
         │  OCI Protocol
         ▼
┌─────────────────────┐
│   Container Registry│
│   (quay.io)         │
│   Model as OCI image│
└─────────────────────┘
```

## Quick Start

```bash
# Deploy
make deploy

# Check status
make status

# Test transcription
make test
```

## Step 1: Create Namespace

```bash
oc new-project models
```

Or apply the namespace manifest:

```bash
oc apply -f manifests/namespace.yaml
```

## Step 2: Create ServingRuntime

The ServingRuntime defines the vLLM container configuration for Whisper models:

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: vllm-rhaiis-whisper
  namespace: models
  annotations:
    opendatahub.io/apiProtocol: REST
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
    openshift.io/display-name: vLLM RHAIIS 3.2.4 (Whisper Support)
  labels:
    opendatahub.io/dashboard: "true"
spec:
  annotations:
    prometheus.io/path: /metrics
    prometheus.io/port: "8080"
  containers:
  - args:
    - --port=8080
    - --model=/mnt/models
    - --served-model-name={{.Name}}
    env:
    - name: HF_HOME
      value: /tmp/hf_home
    - name: HF_HUB_OFFLINE
      value: "1"
    - name: VLLM_NO_USAGE_STATS
      value: "1"
    image: registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.2.4
    name: kserve-container
    ports:
    - containerPort: 8080
      protocol: TCP
    volumeMounts:
    - mountPath: /dev/shm
      name: shm
  multiModel: false
  supportedModelFormats:
  - autoSelect: true
    name: vLLM
  volumes:
  - emptyDir:
      medium: Memory
      sizeLimit: 2Gi
    name: shm
```

Apply:
```bash
oc apply -f manifests/serving-runtime.yaml
```

## Step 3: Create InferenceService

The InferenceService deploys the Whisper model:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: whisper-large-fp8
  namespace: models
  annotations:
    openshift.io/display-name: whisper-large-FP8
    serving.kserve.io/deploymentMode: RawDeployment
  labels:
    networking.kserve.io/visibility: exposed
    opendatahub.io/dashboard: "true"
spec:
  predictor:
    minReplicas: 1
    maxReplicas: 1
    model:
      modelFormat:
        name: vLLM
      runtime: vllm-rhaiis-whisper
      storageUri: oci://quay.io/wjackson/models:redhatai-whisper-large-v3-turbo-FP8-dynamic
      args:
      - --max-model-len=448
      - --max-num-seqs=400
      - --limit-mm-per-prompt
      - '{"audio": 1}'
      - --enforce-eager
      resources:
        requests:
          cpu: "2"
          memory: 8Gi
          nvidia.com/gpu: "1"
        limits:
          cpu: "4"
          memory: 10Gi
          nvidia.com/gpu: "1"
    tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule
```

**Key configuration:**
- `--max-model-len=448` - Whisper's max sequence length (~30 seconds audio)
- `--max-num-seqs=400` - Concurrent sequences for batch processing
- `--limit-mm-per-prompt='{"audio": 1}'` - One audio file per request (JSON format for vLLM 0.11+)
- `--enforce-eager` - Disable CUDA graphs for encoder-decoder models

Apply:
```bash
oc apply -f manifests/inference-service.yaml
```

## Step 4: Wait for Deployment

Monitor the deployment:

```bash
# Watch pods
oc get pods -n models -w

# Check vLLM logs (model loading)
oc logs -f $(oc get pods -n models -l serving.kserve.io/inferenceservice=whisper-large-fp8 -o jsonpath='{.items[0].metadata.name}') -c kserve-container -n models
```

Expected timeline:
- OCI image pull: ~2 minutes
- vLLM initialization: ~1 minute

Look for these log messages:
```
INFO ... Resolved architecture: WhisperForConditionalGeneration
INFO ... Using max model len 448
INFO:     Application startup complete.
```

## Step 5: Get Endpoint

```bash
# Get the route URL
URL=$(oc get route whisper-large-fp8 -n models -o jsonpath='{.spec.host}')
echo "Endpoint: https://$URL"
```

## Step 6: Test the Deployment

### List Models

```bash
curl -sk "https://$URL/v1/models"
```

### Transcribe Audio

```bash
# Transcribe a WAV file
curl -sk "https://$URL/v1/audio/transcriptions" \
  -F file=@audio.wav \
  -F model=whisper-large-fp8 \
  -F response_format=json
```

**Response:**
```json
{
  "text": "Your transcribed text here...",
  "usage": {"type": "duration", "seconds": 60}
}
```

### Supported Audio Formats

- WAV (recommended: 16kHz mono PCM)
- MP3
- M4A
- FLAC
- OGG

### Audio Preprocessing Tips

For best results, convert audio to 16kHz mono WAV:

```bash
ffmpeg -i input.m4a -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```

To extract the first N seconds:

```bash
ffmpeg -i input.m4a -t 60 -acodec pcm_s16le -ar 16000 -ac 1 output_60s.wav
```

## vLLM Version Compatibility

| Image | vLLM Version | Whisper Support | Notes |
|-------|-------------|-----------------|-------|
| RHOAI default (modh) | 0.8.5 | No | Architecture not supported |
| RHAIIS 3.0.0 | 0.8.4 | No | torch.compile bug |
| Community vLLM | 0.8.5+ | Yes | Works |
| **RHAIIS 3.2.4** | **0.11.0+rhai5** | **Yes** | **Recommended** |

**Important:** vLLM 0.11.0+ changed `--limit-mm-per-prompt` format back to JSON (`'{"audio": 1}'`) from the KEY=VALUE format used in 0.8.x.

## Troubleshooting

### Model Architecture Not Supported

If you see:
```
Model architectures ['WhisperForConditionalGeneration'] failed to be inspected
```

Ensure you're using RHAIIS 3.2.4 or community vLLM 0.8.5+, not the default RHOAI vLLM image.

### torch.compile Error

If you see errors related to `@torch.compile(dynamic=True, ...)` during model loading:
```
SyntaxError: ... backend=current_platform.simple_compile_backend ...
```

This indicates RHAIIS 3.0.0 (vLLM 0.8.4) which has a bug with Whisper. Upgrade to RHAIIS 3.2.4.

### limit-mm-per-prompt Format Error

If you see:
```
argument --limit-mm-per-prompt: Value audio=1 cannot be converted to JSON
```

You're using vLLM 0.11+. Change from `--limit-mm-per-prompt=audio=1` to:
```yaml
args:
- --limit-mm-per-prompt
- '{"audio": 1}'
```

### Pod Stuck Pending (Insufficient GPU)

```
0/2 nodes are available: 2 Insufficient nvidia.com/gpu
```

Either wait for a GPU to become available or scale up GPU nodes.

### ServingRuntime Changes Not Taking Effect

Delete the pod to pick up runtime changes:
```bash
oc delete pod -l serving.kserve.io/inferenceservice=whisper-large-fp8 -n models
```

## Model Specifications

| Property | Value |
|----------|-------|
| Model | RedHatAI/whisper-large-v3-turbo-FP8-dynamic |
| Base Model | openai/whisper-large-v3-turbo |
| Quantization | FP8 dynamic |
| Max Audio Length | ~30 seconds per request |
| GPU Memory | ~4GB |
| Languages | 99+ languages |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/v1/audio/transcriptions` | Transcribe audio to text |
| `/v1/audio/translations` | Translate audio to English text |
| `/v1/models` | List available models |
| `/health` | Health check |
| `/metrics` | Prometheus metrics |

## LibreChat Integration

To use Whisper in LibreChat for speech-to-text:

### Create Service Account Token

```bash
oc create sa librechat-whisper -n models
oc adm policy add-role-to-user view -z librechat-whisper -n models
oc create token librechat-whisper -n models --duration=8760h
```

### LibreChat Configuration

Add to `librechat.yaml`:

```yaml
speech:
  stt:
    url: "https://whisper-large-fp8-models.apps.your-cluster.com/v1/audio/transcriptions"
    apiKey: "<YOUR_SERVICE_ACCOUNT_TOKEN>"
    model: "whisper-large-fp8"
```

## References

- [vLLM Audio Support](https://docs.vllm.ai/en/latest/models/supported_models.html#encoder-decoder-language-models)
- [Whisper Model Card](https://huggingface.co/openai/whisper-large-v3-turbo)
- [RedHatAI FP8 Quantized Model](https://huggingface.co/RedHatAI/whisper-large-v3-turbo-FP8-dynamic)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
