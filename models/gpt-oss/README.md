# GPT-OSS Deployment Guide for OpenShift AI

This guide covers deploying the RedHatAI/gpt-oss-20b model on OpenShift AI using the RHAIIS vLLM CUDA runtime with S3/Noobaa storage and tool calling support.

## Prerequisites

- OpenShift cluster with OpenShift AI installed
- GPU node(s) with NVIDIA GPU Operator configured
- OpenShift Data Foundation (ODF) with Noobaa for S3 storage
- Access to `registry.redhat.io/rhaiis/vllm-cuda-rhel9` images

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      OpenShift AI                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  KServe InferenceService                                 ││
│  │  ┌─────────────────────┐  ┌─────────────────────┐       ││
│  │  │ storage-initializer │  │   kserve-container  │       ││
│  │  │   (init container)  │──│   (vLLM + model)    │       ││
│  │  │   Downloads from S3 │  │   Serves API        │       ││
│  │  └──────────┬──────────┘  └──────────┬──────────┘       ││
│  │             │ /mnt/models            │ :8080            ││
│  └─────────────│────────────────────────│──────────────────┘│
│                │                        │                   │
│  ┌─────────────▼────────────────────────▼──────────────────┐│
│  │              ServingRuntime                              ││
│  │  - vLLM CUDA runtime                                     ││
│  │  - Tool calling enabled                                  ││
│  │  - OpenAI-compatible API                                 ││
│  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
         │
         │  S3 Protocol
         ▼
┌─────────────────────┐
│   Noobaa/ODF        │
│   S3 Bucket         │
│   (Model Storage)   │
└─────────────────────┘
```

## Step 1: Create Namespace

```bash
oc new-project gpt-oss
```

## Step 2: Upload Model to S3

The GPT-OSS-20b model requires the `o200k_base.tiktoken` vocabulary file alongside the model weights.

### Option A: Stream from HuggingFace to S3

**First, set S3 credentials as environment variables:**

```bash
export S3_ENDPOINT='https://s3-openshift-storage.apps.your-cluster.com'
export AWS_ACCESS_KEY_ID='your-access-key'
export AWS_SECRET_ACCESS_KEY='your-secret-key'
export S3_BUCKET='your-bucket-name'

# Or copy and source from the example file
cp ../models/.env.example .env
# Edit .env with your values
source .env
```

Then run the provided script:

```bash
python scripts/stream_to_s3.py
# or
python scripts/download_and_upload.py
```

These scripts read credentials from environment variables. See `models/.env.example` for a template.

Alternatively, create your own `stream_to_s3.py`:

```python
#!/usr/bin/env python3
"""Stream GPT-OSS-20b from HuggingFace directly to S3 without local storage."""

import os
import boto3
from huggingface_hub import HfFileSystem, hf_hub_url
import requests

# Configuration
MODEL_ID = "RedHatAI/gpt-oss-20b"
S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
S3_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT")
S3_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
S3_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
S3_PREFIX = "gpt-oss-models/gpt-oss-20b"

# Initialize S3 client
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    verify=False,  # For self-signed certs
)

# Get file list from HuggingFace
fs = HfFileSystem()
files = fs.ls(f"{MODEL_ID}", detail=True)

for file_info in files:
    if file_info["type"] != "file":
        continue

    filename = file_info["name"].split("/")[-1]
    s3_key = f"{S3_PREFIX}/{filename}"

    # Stream from HuggingFace to S3
    url = hf_hub_url(MODEL_ID, filename)
    print(f"Streaming {filename} to s3://{S3_BUCKET}/{s3_key}...")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        s3.upload_fileobj(r.raw, S3_BUCKET, s3_key)

    print(f"  Uploaded {filename}")

# Download and upload tiktoken vocabulary file
print("Downloading tiktoken vocabulary...")
import tiktoken
enc = tiktoken.get_encoding("o200k_base")
tiktoken_path = enc._mergeable_ranks
# The file is cached locally by tiktoken, upload it
tiktoken_cache = os.path.expanduser("~/.cache/tiktoken/o200k_base.tiktoken")
if os.path.exists(tiktoken_cache):
    s3.upload_file(tiktoken_cache, S3_BUCKET, f"{S3_PREFIX}/o200k_base.tiktoken")
    print("Uploaded o200k_base.tiktoken")

print("Upload complete!")
```

Run with environment variables set:
```bash
export AWS_S3_BUCKET="your-bucket-name"
export AWS_S3_ENDPOINT="https://s3-openshift-storage.apps.your-cluster.com"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
python stream_to_s3.py
```

### Option B: Download Locally First

```bash
# Download model
huggingface-cli download RedHatAI/gpt-oss-20b --local-dir ./gpt-oss-20b

# Download tiktoken vocabulary
python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
cp ~/.cache/tiktoken/o200k_base.tiktoken ./gpt-oss-20b/

# Upload to S3 using AWS CLI or boto3
aws s3 cp --recursive ./gpt-oss-20b s3://${AWS_S3_BUCKET}/gpt-oss-models/gpt-oss-20b/ \
    --endpoint-url ${AWS_S3_ENDPOINT}
```

## Step 3: Create S3 Data Connection Secret

Create `data-connection-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-connection-model-storage
  namespace: gpt-oss
  labels:
    opendatahub.io/dashboard: "true"
    opendatahub.io/managed: "true"
  annotations:
    opendatahub.io/connection-type: s3
    openshift.io/display-name: Model Storage (Noobaa)
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "YOUR_ACCESS_KEY"
  AWS_SECRET_ACCESS_KEY: "YOUR_SECRET_KEY"
  AWS_DEFAULT_REGION: ""
  AWS_S3_BUCKET: "YOUR_BUCKET_NAME"
  AWS_S3_ENDPOINT: "https://s3-openshift-storage.apps.your-cluster.com"
```

Apply:
```bash
oc apply -f data-connection-secret.yaml -n gpt-oss
```

## Step 4: Create ServingRuntime

Create the ServingRuntime through the OpenShift AI dashboard:

1. Go to OpenShift AI Dashboard → Model Serving → ServingRuntimes
2. Create a new ServingRuntime with:
   - Name: `gpt-oss-20b-rhaiis`
   - Runtime: RHAIIS NVIDIA GPU ServingRuntime for KServe
   - Image: `registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.2.4`

Or create via YAML:

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: gpt-oss-20b-rhaiis
  namespace: gpt-oss
  annotations:
    opendatahub.io/accelerator-name: migrated-gpu
    opendatahub.io/apiProtocol: REST
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
    opendatahub.io/template-display-name: RHAIIS NVIDIA GPU ServingRuntime
    opendatahub.io/template-name: rhaiis-cuda-runtime
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
    - --tool-call-parser=openai
    - --enable-auto-tool-choice
    command:
    - python
    - -m
    - vllm.entrypoints.openai.api_server
    env:
    - name: HF_HOME
      value: /tmp/hf_home
    - name: HF_HUB_OFFLINE
      value: "1"
    - name: VLLM_NO_USAGE_STATS
      value: "1"
    - name: TIKTOKEN_ENCODINGS_BASE
      value: /mnt/models
    - name: VLLM_CACHE_DIR
      value: /tmp/vllm
    - name: TRANSFORMERS_CACHE
      value: /tmp/transformers
    - name: XDG_CACHE_HOME
      value: /tmp
    - name: HOME
      value: /tmp
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

**Critical environment variable:**
- `TIKTOKEN_ENCODINGS_BASE: /mnt/models` - Tells tiktoken to look for `o200k_base.tiktoken` in the model directory

**Tool calling args:**
- `--tool-call-parser=openai` - Uses OpenAI's tool call format
- `--enable-auto-tool-choice` - Enables automatic tool selection

Apply:
```bash
oc apply -f servingruntime.yaml -n gpt-oss
```

## Step 5: Create InferenceService

Create `inference-service-s3.yaml`:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: gpt-oss-20b-rhaiis
  namespace: gpt-oss
  annotations:
    openshift.io/display-name: gpt-oss-20b-rhaiis
    security.opendatahub.io/enable-auth: "true"
    serving.kserve.io/deploymentMode: RawDeployment
  labels:
    networking.kserve.io/visibility: exposed
    opendatahub.io/dashboard: "true"
spec:
  predictor:
    maxReplicas: 1
    minReplicas: 1
    tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
    model:
      modelFormat:
        name: vLLM
      runtime: gpt-oss-20b-rhaiis
      env:
        - name: TIKTOKEN_ENCODINGS_BASE
          value: /mnt/models
      storage:
        key: aws-connection-model-storage
        path: gpt-oss-models/gpt-oss-20b
      resources:
        requests:
          cpu: "4"
          memory: 24Gi
          nvidia.com/gpu: "1"
        limits:
          cpu: "8"
          memory: 32Gi
          nvidia.com/gpu: "1"
```

Apply:
```bash
oc apply -f inference-service-s3.yaml -n gpt-oss
```

## Step 6: Wait for Deployment

Monitor the deployment:

```bash
# Watch pods
oc get pods -n gpt-oss -w

# Check storage initializer logs (model download from S3)
oc logs -f $(oc get pods -n gpt-oss -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -o jsonpath='{.items[0].metadata.name}') -c storage-initializer -n gpt-oss

# Check vLLM logs (model loading)
oc logs -f $(oc get pods -n gpt-oss -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -o jsonpath='{.items[0].metadata.name}') -c kserve-container -n gpt-oss
```

Expected timeline:
- S3 download: ~10 minutes (38.5GB)
- vLLM initialization: ~3 minutes (model loading + CUDA graph capture)

Look for these log messages:
```
INFO ... Supported_tasks: ['generate']
INFO ... "auto" tool choice has been enabled
INFO ... Starting vLLM API server on http://0.0.0.0:8080
```

## Step 7: Get Endpoint and Token

```bash
# Get the route URL
URL=$(oc get route gpt-oss-20b-rhaiis -n gpt-oss -o jsonpath='{.spec.host}')
echo "Endpoint: https://$URL"

# Get authentication token
TOKEN=$(oc whoami -t)
echo "Token: $TOKEN"
```

## Step 8: Test the Deployment

### Basic Chat Completion

```bash
curl -sk "https://$URL/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-20b-rhaiis",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

### Tool Calling Test

```bash
curl -sk "https://$URL/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-20b-rhaiis",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant with access to tools."},
      {"role": "user", "content": "What is the weather in San Francisco?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get the current weather for a location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": {"type": "string", "description": "City and state"},
              "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["location"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "max_tokens": 200
  }'
```

Expected response with tool call:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "chatcmpl-tool-...",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"San Francisco, CA\", \"unit\": \"fahrenheit\"}"
        }
      }],
      "reasoning_content": "User asks for weather in San Francisco. We should use get_weather function."
    },
    "finish_reason": "tool_calls"
  }]
}
```

## Troubleshooting

### Model Not Found / Tiktoken Error

If you see tiktoken errors, ensure:
1. `o200k_base.tiktoken` is uploaded to S3 alongside model files
2. `TIKTOKEN_ENCODINGS_BASE=/mnt/models` is set in both ServingRuntime and InferenceService

### Tool Calls in Content Field Instead of tool_calls Array

Add these args to the ServingRuntime container:
```yaml
args:
  - --tool-call-parser=openai
  - --enable-auto-tool-choice
```

Then restart the pod:
```bash
oc delete pod -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -n gpt-oss
```

### OAuth Authentication Required

The endpoint requires bearer token authentication:
```bash
TOKEN=$(oc whoami -t)
curl -H "Authorization: Bearer $TOKEN" ...
```

### ServingRuntime Changes Not Taking Effect

ServingRuntime changes don't automatically restart pods. Delete the pod:
```bash
oc delete pod -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -n gpt-oss
```

> **WARNING: Never use `kubectl rollout restart` on KServe deployments!**
>
> KServe manages deployments through the InferenceService controller. Running `kubectl rollout restart deployment/...` adds a `kubectl.kubernetes.io/restartedAt` annotation that conflicts with KServe's reconciliation loop, causing:
> - Infinite deployment generations (thousands per hour)
> - Constant ReplicaSet churn
> - InferenceService showing `READY=False` even when pods are working
>
> **Always use pod deletion instead:**
> ```bash
> oc delete pod -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -n gpt-oss
> ```
>
> If you accidentally ran `rollout restart`, fix it by removing the annotation:
> ```bash
> kubectl patch deployment gpt-oss-20b-rhaiis-predictor -n gpt-oss --type=json \
>   -p='[{"op": "remove", "path": "/spec/template/metadata/annotations/kubectl.kubernetes.io~1restartedAt"}]'
> ```

### Pod Stuck in Init:0/1

This usually means the S3 download is still in progress. Check logs:
```bash
oc logs -f <pod-name> -c storage-initializer -n gpt-oss
```

## Model Specifications

| Property | Value |
|----------|-------|
| Model | RedHatAI/gpt-oss-20b |
| Size | ~38.5GB (19 files) |
| Quantization | mxfp4 (Marlin backend) |
| Context Length | 131,072 tokens |
| GPU Memory | ~14GB |
| Features | Tool calling, reasoning traces |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| `/v1/completions` | Text completions |
| `/v1/models` | List available models |
| `/health` | Health check |
| `/metrics` | Prometheus metrics |

## LibreChat Integration

To use GPT-OSS-20b as an endpoint in LibreChat, you need a long-lived service account token (user tokens expire).

### Create Service Account with Long-Lived Token

```bash
# Create service account
oc create sa librechat-gpt-oss -n gpt-oss

# Grant view access (required for authentication)
oc adm policy add-role-to-user view -z librechat-gpt-oss -n gpt-oss

# Create long-lived token (1 year)
oc create token librechat-gpt-oss -n gpt-oss --duration=8760h
```

Save the generated token for use in LibreChat configuration.

### LibreChat YAML Configuration

Add this to your LibreChat `librechat.yaml` under `endpoints.custom`:

```yaml
endpoints:
  custom:
    - name: "GPT-OSS-20b"
      apiKey: "<YOUR_SERVICE_ACCOUNT_TOKEN>"
      baseURL: "https://gpt-oss-20b-rhaiis-gpt-oss.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com/v1"
      models:
        default: ["gpt-oss-20b-rhaiis"]
        fetch: true
      titleConvo: true
      titleModel: "gpt-oss-20b-rhaiis"
      summarize: false
      summaryModel: "gpt-oss-20b-rhaiis"
      forcePrompt: false
      modelDisplayLabel: "GPT-OSS-20b"
      iconURL: "https://www.redhat.com/favicon.ico"
```

### With Tool Calling Support

If you want to enable tool calling in LibreChat, add the `features` block:

```yaml
endpoints:
  custom:
    - name: "GPT-OSS-20b"
      apiKey: "<YOUR_SERVICE_ACCOUNT_TOKEN>"
      baseURL: "https://gpt-oss-20b-rhaiis-gpt-oss.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com/v1"
      models:
        default: ["gpt-oss-20b-rhaiis"]
        fetch: true
      titleConvo: true
      titleModel: "gpt-oss-20b-rhaiis"
      summarize: false
      summaryModel: "gpt-oss-20b-rhaiis"
      forcePrompt: false
      modelDisplayLabel: "GPT-OSS-20b"
      iconURL: "https://www.redhat.com/favicon.ico"
      features:
        toolCalls: true
```

### Verify Token Works

Test the service account token before adding to LibreChat:

```bash
SA_TOKEN="<YOUR_SERVICE_ACCOUNT_TOKEN>"
URL="https://gpt-oss-20b-rhaiis-gpt-oss.apps.cluster-mqwwr.mqwwr.sandbox1259.opentlc.com"

curl -sk "${URL}/v1/models" -H "Authorization: Bearer ${SA_TOKEN}"
```

### Token Renewal

The token expires after the duration specified (default: 1 year). To renew:

```bash
# Generate new token
oc create token librechat-gpt-oss -n gpt-oss --duration=8760h

# Update LibreChat configuration with new token
# Restart LibreChat to pick up the change
```

### Troubleshooting: ByteString Error

If you see this error in LibreChat when using the GPT-OSS endpoint:

```
An error occurred while processing the request: Cannot convert argument to a ByteString
because the character at index 1035 has a value of 65533 which is greater than 255.
```

**Root Cause:** The service account token stored in the Kubernetes secret has become corrupted. Character 65533 (U+FFFD) is the Unicode replacement character, indicating encoding corruption. This can happen during copy/paste operations or when storing the token in a secret.

**Diagnosis:** Check for corrupted bytes in the token:

```bash
# Get the token from the secret and check for non-ASCII characters
oc get secret librechat-credentials-env -n librechat -o jsonpath='{.data.GPT_OSS_API_KEY}' | base64 -d | xxd | grep -E '[89a-f][0-9a-f] [89a-f]'
```

If you see byte sequences like `c7 07` or other non-ASCII bytes in what should be a pure ASCII JWT token, the token is corrupted.

**Fix:** Regenerate the token and update the secret:

```bash
# Generate a fresh token
NEW_TOKEN=$(oc create token librechat-gpt-oss -n gpt-oss --duration=8760h)

# Verify it's clean ASCII
echo "$NEW_TOKEN" | od -c | grep -v '[a-zA-Z0-9._-]' || echo "Token is clean"

# Update the secret
oc patch secret librechat-credentials-env -n librechat --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/GPT_OSS_API_KEY\", \"value\": \"$(echo -n "$NEW_TOKEN" | base64)\"}]"

# Restart LibreChat
oc rollout restart deployment/librechat-librechat -n librechat
```

**Prevention:** When storing tokens in secrets, always use `echo -n` (no newline) and pipe directly to base64 encoding to avoid introducing extra characters.

## References

- [vLLM Tool Calling Documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#tool-calling-in-the-chat-completion-api)
- [GPT-OSS Model Card](https://huggingface.co/RedHatAI/gpt-oss-20b)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [LibreChat Custom Endpoints](https://www.librechat.ai/docs/configuration/librechat_yaml/ai_endpoints/custom)
