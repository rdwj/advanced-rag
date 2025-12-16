# Pyannote Speaker Diarization Server

FastAPI server for speaker diarization using pyannote-audio, designed for FIPS-compliant OpenShift clusters.

## Features

- **Speaker Diarization**: Identify "who spoke when" in audio recordings
- **Voice Activity Detection**: Detect speech segments in audio
- **GPU Acceleration**: NVIDIA CUDA support for fast inference
- **FIPS Compliance**: UBI9 base image for enterprise environments
- **OpenAI-style API**: RESTful endpoints for easy integration

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      OpenShift Cluster                        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  pyannote-server Deployment                              │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │   FastAPI Server (UBI9 + Python 3.11)               │ │ │
│  │  │   - pyannote.audio 4.x                              │ │ │
│  │  │   - PyTorch 2.x + CUDA                              │ │ │
│  │  │   - soundfile for audio I/O                         │ │ │
│  │  └──────────────────────┬──────────────────────────────┘ │ │
│  │                         │ :8080                          │ │
│  └─────────────────────────│────────────────────────────────┘ │
│                            │                                  │
│  ┌─────────────────────────▼────────────────────────────────┐ │
│  │  Route (TLS edge termination)                            │ │
│  │  https://pyannote-server-<namespace>.apps.<cluster>      │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │
         │  Model download on startup
         ▼
┌─────────────────────┐
│   HuggingFace Hub   │
│   pyannote/speaker- │
│   diarization-3.1   │
└─────────────────────┘
```

## Quick Start

```bash
# Set your HuggingFace token (required for model download)
export HF_TOKEN=hf_your_token_here

# Deploy to default namespace (models)
make deploy

# Check status
make status

# Test the service
make test
```

## Prerequisites

1. **OpenShift cluster** with:
   - GPU node(s) with NVIDIA GPU Operator configured
   - OpenShift AI installed (optional, for dashboard integration)

2. **HuggingFace account** with:
   - Accepted license terms for [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - API token from [HuggingFace settings](https://huggingface.co/settings/tokens)

3. **Container image** built and pushed to your registry:
   ```bash
   make build REGISTRY=quay.io/yourorg
   make push REGISTRY=quay.io/yourorg
   ```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NAMESPACE` | `models` | OpenShift namespace for deployment |
| `REGISTRY` | `quay.io/wjackson` | Container registry for the image |
| `IMAGE_TAG` | `latest` | Container image tag |
| `HF_TOKEN` | (required) | HuggingFace API token |
| `PULL_SECRET` | `pyannote-pull-secret` | Image pull secret name |

### Makefile Targets

```bash
make help              # Show all available targets

# Deployment
make deploy            # Deploy pyannote server
make undeploy          # Remove deployment

# Build
make build             # Build container image (requires ec2-dev)
make push              # Push image to registry

# Status & Testing
make status            # Show deployment status
make logs              # Show pod logs
make test              # Test health endpoint
make test-diarize      # Test diarization with sample audio
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with model status |
| `/ready` | GET | Readiness probe for Kubernetes |
| `/v1/diarize` | POST | Speaker diarization |
| `/v1/vad` | POST | Voice activity detection |

### Health Check

```bash
curl -sk "https://$ENDPOINT/health"
```

Response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda"
}
```

### Speaker Diarization

```bash
# Basic diarization
curl -sk "https://$ENDPOINT/v1/diarize" \
  -F "file=@audio.wav"

# With speaker count hints
curl -sk "https://$ENDPOINT/v1/diarize" \
  -F "file=@audio.wav" \
  -F "num_speakers=2"

# With speaker range
curl -sk "https://$ENDPOINT/v1/diarize" \
  -F "file=@audio.wav" \
  -F "min_speakers=2" \
  -F "max_speakers=5"
```

Response:
```json
{
  "segments": [
    {"start": 0.5, "end": 2.3, "speaker": "SPEAKER_00"},
    {"start": 2.8, "end": 5.1, "speaker": "SPEAKER_01"},
    {"start": 5.5, "end": 8.2, "speaker": "SPEAKER_00"}
  ],
  "num_speakers": 2
}
```

### Voice Activity Detection

```bash
curl -sk "https://$ENDPOINT/v1/vad" \
  -F "file=@audio.wav"
```

Response:
```json
{
  "speech_segments": [
    {"start": 0.5, "end": 8.2},
    {"start": 10.1, "end": 15.3}
  ]
}
```

## Audio Format Requirements

**Supported format**: WAV (recommended: 16kHz mono PCM)

The server uses `soundfile` for audio loading, which supports WAV files via libsndfile.

**Convert other formats** before uploading:

```bash
# Convert M4A to WAV
ffmpeg -i input.m4a -ar 16000 -ac 1 output.wav

# Convert MP3 to WAV
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav

# Extract first 60 seconds
ffmpeg -i input.m4a -t 60 -ar 16000 -ac 1 output_60s.wav
```

## Building the Container

The container must be built on an x86_64 Linux system (not Mac ARM64) for OpenShift deployment.

### Using ec2-dev (Recommended)

```bash
# Build on ec2-dev and push to registry
make build REGISTRY=quay.io/yourorg
make push REGISTRY=quay.io/yourorg
```

### Manual Build

```bash
# On x86_64 Linux
podman build -t quay.io/yourorg/pyannote:latest -f Containerfile .
podman push quay.io/yourorg/pyannote:latest
```

## Deployment Details

### Secrets

The deployment requires a HuggingFace token secret:

```bash
# Create the secret
oc create secret generic pyannote-hf-token \
  --from-literal=token=$HF_TOKEN \
  -n models
```

Or use the Makefile:

```bash
export HF_TOKEN=hf_your_token
make create-secret
```

### Image Pull Secret (Optional)

If using a private registry:

```bash
# Create pull secret from existing docker config
oc create secret generic pyannote-pull-secret \
  --from-file=.dockerconfigjson=$HOME/.docker/config.json \
  --type=kubernetes.io/dockerconfigjson \
  -n models

# Or link existing secret
oc secrets link default pyannote-pull-secret --for=pull -n models
```

### Resource Requirements

| Resource | Request | Limit |
|----------|---------|-------|
| CPU | 1 core | 4 cores |
| Memory | 4Gi | 8Gi |
| GPU | 1x NVIDIA | 1x NVIDIA |
| GPU VRAM | ~4-6GB | - |

## Troubleshooting

### Model Not Loading

Check pod logs for HuggingFace authentication errors:

```bash
make logs
```

Common issues:
- HF_TOKEN not set or invalid
- License not accepted on HuggingFace
- Network connectivity to huggingface.co blocked

### GPU Not Available

```bash
# Check GPU nodes
oc get nodes -l nvidia.com/gpu.present=true

# Check GPU allocatable
oc describe node <gpu-node> | grep -A5 "Allocatable:"
```

### Audio Decoding Errors

The server uses `soundfile` (libsndfile) for audio loading. Ensure:
- Audio is in WAV format (not M4A, MP3, etc.)
- Convert using FFmpeg before uploading

### Pod Stuck Pending

```bash
# Check events
oc describe pod -l app=pyannote-server -n models | grep -A20 Events

# Common causes:
# - Insufficient GPU resources
# - Image pull failures (check pull secret)
# - PVC not bound
```

## Model Information

| Property | Value |
|----------|-------|
| Model | pyannote/speaker-diarization-3.1 |
| Framework | pyannote.audio 4.x |
| GPU Memory | ~4-6GB VRAM |
| Languages | Language-agnostic (works with any language) |
| Max Audio Length | Limited by GPU memory (~hours for 8GB VRAM) |

## Integration Examples

### With Whisper for Full Transcription Pipeline

```python
import requests

# 1. Transcribe audio with Whisper
whisper_response = requests.post(
    "https://whisper-endpoint/v1/audio/transcriptions",
    files={"file": open("audio.wav", "rb")},
    data={"model": "whisper-large-fp8"}
)
transcript = whisper_response.json()["text"]

# 2. Get speaker segments with Pyannote
diarization_response = requests.post(
    "https://pyannote-endpoint/v1/diarize",
    files={"file": open("audio.wav", "rb")}
)
segments = diarization_response.json()["segments"]

# 3. Combine transcript with speaker labels
# (requires word-level timestamps from Whisper)
```

### LibreChat Integration

Pyannote can be used in LibreChat for speaker identification in audio uploads. Configure in `librechat.yaml`:

```yaml
# Custom endpoint for diarization
endpoints:
  custom:
    - name: "Speaker Diarization"
      apiKey: "${PYANNOTE_API_KEY}"
      baseURL: "https://pyannote-server-models.apps.cluster.example.com"
```

## File Structure

```
pyannote/
├── Containerfile           # Container build file (UBI9 base)
├── requirements.txt        # Python dependencies
├── Makefile               # Deployment and management commands
├── deploy.sh              # Deployment script
├── README.md              # This file
├── src/
│   └── server.py          # FastAPI application
└── manifests/
    ├── namespace.yaml     # Namespace definition
    ├── deployment.yaml    # Deployment, Service, Route
    ├── pvc.yaml          # PersistentVolumeClaim (optional)
    └── secret.yaml.example # HuggingFace token secret template
```

## References

- [pyannote-audio Documentation](https://github.com/pyannote/pyannote-audio)
- [Speaker Diarization 3.1 Model](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
