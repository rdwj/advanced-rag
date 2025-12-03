# Chunker Service

Go-based sliding window text chunker exposed as an HTTP service. Provides fast, configurable text chunking for RAG pipelines.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check - returns `{"status": "ok"}` |
| `/chunk` | POST | Chunk text using sliding window algorithm |

### Chunk Request

```json
{
  "text": "Your text to chunk...",
  "plan": {
    "window_size": 200,
    "overlap": 40,
    "mode": "tokens",
    "break_on_headings": false,
    "max_chunks": 0
  },
  "meta": {
    "file_name": "doc.txt",
    "file_path": "/path/doc.txt",
    "mime_type": "text/plain"
  }
}
```

### Chunk Response

Returns JSON array of chunks with metadata.

## Local Development

```bash
cd services/chunker_service

# Run server directly
go run ./cmd/chunker-server

# Or build and run
go build -o chunker-server ./cmd/chunker-server
./chunker-server
```

Server listens on port 8080 by default.

### Building the CLI for Pipeline Use

The Python pipeline can use a local CLI binary when the chunker service is not available:

```bash
cd services/chunker_service
go build -o ../../bin/chunker ./cmd/chunker
```

## Container Build

Build from within the `chunker_service` directory (self-contained):

```bash
cd services/chunker_service

# Local build (for testing)
podman build -t chunker-service:local -f Containerfile .

# Build for OpenShift (x86_64) - from Mac, use remote build on ec2-dev:
rsync -avz --exclude='.git' . ec2-dev:~/builds/chunker-service/
ssh ec2-dev 'cd ~/builds/chunker-service && podman build -t chunker-service:latest -f Containerfile .'
```

## OpenShift Deployment

### Prerequisites

- OpenShift cluster access
- Container image pushed to accessible registry

### Push to OpenShift Registry

```bash
# Get registry route and token
REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}')
OC_TOKEN=$(oc whoami -t)

# Login from build machine
podman login -u unused -p ${OC_TOKEN} ${REGISTRY} --tls-verify=false

# Tag and push
podman tag chunker-service:latest ${REGISTRY}/advanced-rag/chunker-service:latest
podman push --tls-verify=false ${REGISTRY}/advanced-rag/chunker-service:latest
```

### Deploy

```bash
# Create ImageStream (first time only)
oc create imagestream chunker-service -n advanced-rag 2>/dev/null || true

# Apply deployment manifests
oc apply -f manifests/deployment.yaml -n advanced-rag

# Wait for deployment
oc wait --for=condition=Available deployment/chunker-service -n advanced-rag --timeout=120s

# Get route URL
oc get route chunker-service -n advanced-rag -o jsonpath='{.spec.host}'
```

### Verify

```bash
CHUNKER_URL=$(oc get route chunker-service -n advanced-rag -o jsonpath='{.spec.host}')

# Health check
curl -s "https://${CHUNKER_URL}/healthz" | jq .

# Test chunking
curl -X POST "https://${CHUNKER_URL}/chunk" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test document. It contains multiple sentences. Each sentence should be chunked appropriately based on the plan settings.",
    "plan": {"window_size": 50, "overlap": 10, "mode": "tokens"},
    "meta": {"file_name": "test.txt"}
  }'
```

## Configuration

The chunker service is stateless and requires no environment variables. All chunking behavior is controlled through the request payload.

### Chunking Plan Options

| Field | Type | Description |
|-------|------|-------------|
| `window_size` | int | Chunk size (required, > 0) |
| `overlap` | int | Overlap between chunks |
| `mode` | string | "tokens" or "chars" |
| `break_on_headings` | bool | Split on markdown headings |
| `max_chunks` | int | Limit chunks (0 = unlimited) |

## Wiring into Python Pipeline

Set environment variable to prefer the service:

```bash
export CHUNKER_SERVICE_URL=http://chunker-service.advanced-rag.svc.cluster.local:8080
```

`python/rag_pipeline/chunk.py` will POST to the service when this is set; falls back to local CLI otherwise.

## Internal Service URL

```
http://chunker-service.advanced-rag.svc.cluster.local:8080
```

## File Structure

```
services/chunker_service/
├── cmd/
│   ├── chunker/            # CLI tool for local pipeline use
│   └── chunker-server/     # HTTP server
├── pkg/chunking/           # Chunking logic
├── go.mod                  # Go module definition
├── Containerfile           # Container build (self-contained)
├── manifests/
│   └── deployment.yaml     # OpenShift deployment manifests
└── README.md               # This file
```

## Notes

- Go binary is statically compiled (~8MB)
- Uses UBI9 micro image for minimal footprint
- No external dependencies at runtime
- Designed for high-throughput chunking operations
- Service is self-contained for future repo separation
