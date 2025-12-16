# Faster-Whisper Transcription Service

FastAPI service providing audio transcription with word-level timestamps using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Outputs OpenAI-compatible `verbose_json` format with words nested inside segments.

## Features

- **Word-level timestamps** for speaker diarization alignment
- **Medium model** by default (configurable)
- **GPU accelerated** with CUDA support
- **Cluster-internal** service (no external Route)
- **OpenShift ready** with GPU tolerations and timeslicing support

## Response Format

```json
{
  "task": "transcribe",
  "language": "en",
  "duration": 10.52,
  "text": "Hello world, how are you today?",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.48,
      "text": "Hello world,",
      "avg_logprob": -0.25,
      "no_speech_prob": 0.01,
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.42, "probability": 0.98},
        {"word": "world,", "start": 0.52, "end": 0.91, "probability": 0.95}
      ]
    }
  ]
}
```

## Deployment

### Prerequisites

- OpenShift cluster with GPU nodes
- GPU timeslicing configured (optional, for sharing GPU with other services)
- Access to `quay.io/wjackson/faster-whisper` or build your own image

### Build Container Image

**Remote build (recommended for Mac users):**

```bash
make build    # Builds on ec2-dev for x86_64 compatibility
make push     # Pushes from ec2-dev to quay.io
```

**Local build:**

```bash
make build-local  # May have architecture issues on Mac
make push-local
```

### Deploy to OpenShift

```bash
# Create namespace and deploy
make deploy NAMESPACE=faster-whisper

# Check status
make status

# View logs
make logs
```

### Manual Deployment

```bash
# Create namespace
oc new-project faster-whisper

# Deploy resources
oc apply -k manifests/ -n faster-whisper

# Wait for pod to be ready
oc rollout status deployment/faster-whisper -n faster-whisper
```

## Usage

### From Within Cluster

Other services can call faster-whisper at:

```
http://faster-whisper.faster-whisper.svc.cluster.local:8080/transcribe
```

### Local Testing (Port Forward)

```bash
# Start port forward
make port-forward

# In another terminal, test transcription
curl -X POST http://localhost:8080/transcribe \
  -F "file=@test.wav"

# With language hint
curl -X POST "http://localhost:8080/transcribe?language=en" \
  -F "file=@test.wav"
```

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_size": "medium",
  "device": "cuda",
  "compute_type": "float16"
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcribe` | POST | Transcribe audio file (multipart/form-data) |
| `/health` | GET | Health check with model status |
| `/ready` | GET | Readiness probe |
| `/` | GET | Service info |

### POST /transcribe

**Query Parameters:**
- `language` (optional): Language code (e.g., `en`, `es`). Auto-detects if not specified.

**Body:** `multipart/form-data` with `file` field

**Supported Formats:** wav, mp3, m4a, flac, ogg, webm, mp4

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MODEL_SIZE` | `medium` | Whisper model size (tiny, base, small, medium, large-v3) |
| `DEVICE` | `cuda` | Compute device (cuda, cpu) |
| `COMPUTE_TYPE` | `float16` | Precision (float16, int8, float32) |
| `MODEL_PATH` | `/mnt/models` | Model cache directory |

## Resource Requirements

- **GPU**: 1x NVIDIA GPU (~3GB VRAM for medium model)
- **Memory**: 4Gi request, 8Gi limit
- **CPU**: 1 core request, 4 cores limit
- **Storage**: 5Gi PVC for model cache

## Integration with Pyannote

This service is designed to work alongside pyannote-server for speaker diarization. The word-level timestamps enable precise alignment of transcribed words with speaker segments.

Typical workflow:
1. **pyannote-server**: Identify speaker segments with timestamps
2. **faster-whisper**: Transcribe audio with word timestamps
3. **Orchestrator**: Align words to speakers based on timestamp overlap

## Files

```
faster-whisper/
├── src/
│   ├── __init__.py
│   ├── server.py          # FastAPI application
│   ├── transcribe.py      # faster-whisper wrapper
│   └── models.py          # Pydantic response models
├── tests/
│   ├── conftest.py
│   └── test_models.py
├── manifests/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   └── pvc.yaml
├── Containerfile
├── requirements.txt
├── Makefile
└── README.md
```

## Troubleshooting

### Pod not starting

Check if GPU is available:
```bash
oc describe pod -l app=faster-whisper -n faster-whisper | grep -A5 Events
```

### Model download slow

First startup downloads the model (~1.5GB for medium). Subsequent starts use the cached model from PVC.

### Out of memory

If running alongside other GPU workloads, ensure timeslicing is configured or reduce model size:
```yaml
env:
  - name: MODEL_SIZE
    value: "small"  # Uses less VRAM
```
