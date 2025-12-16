# Milvus Vector Database

Open-source vector database optimized for similarity search and AI applications.

Part of [databases](../README.md).

## Features

- Native hybrid search (dense vectors + BM25 sparse)
- High-performance similarity search with HNSW and IVF indexes
- Scalable architecture with distributed deployment options
- Built-in MinIO integration for object storage

## Local Development

### Quick Start

```bash
cd local
./podman_milvus.sh start
curl -s http://localhost:9091/healthz   # expect OK
```

### Exposed Ports

| Service | Port | Description |
|---------|------|-------------|
| Milvus gRPC | 19530 | Primary API endpoint |
| Milvus Metrics | 9091 | Health checks and metrics |
| MinIO API | 9000 | Object storage API |
| MinIO Console | 9090 | Web UI (admin/minioadmin) |

### Common Commands

```bash
./podman_milvus.sh start    # Start or ensure pod is running
./podman_milvus.sh stop     # Stop all containers
./podman_milvus.sh status   # Show status summary
./podman_milvus.sh logs     # View Milvus logs
./podman_milvus.sh health   # Health check only
./podman_milvus.sh destroy  # Tear down (data preserved in ./data)
```

### Environment Overrides

Customize via environment variables:
- `POD_NAME` - Pod name (default: milvus-pod)
- `MILVUS_IMAGE` - Milvus image (default: milvusdb/milvus:v2.4.4)
- `MILVUS_GRPC_PORT` - gRPC port (default: 19530)
- `MILVUS_DATA_DIR` - Data directory (default: ./data/milvus)

## OpenShift Deployment

See [openshift/OPENSHIFT_DEPLOYMENT.md](openshift/OPENSHIFT_DEPLOYMENT.md) for detailed instructions.

### Quick Deploy

```bash
# Set your namespace
NAMESPACE=milvus  # Change to your desired namespace

# Using Helm (recommended for production)
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo update

# Grant SCCs before deploying
oc create namespace $NAMESPACE
oc adm policy add-scc-to-user anyuid -z default -n $NAMESPACE
oc adm policy add-scc-to-user anyuid -z milvus-minio -n $NAMESPACE

# Install with OpenShift values
helm install milvus milvus/milvus \
  -f openshift/values-openshift.yaml \
  -n $NAMESPACE

# Wait for pods
oc wait --for=condition=Ready pods -l app.kubernetes.io/name=milvus -n $NAMESPACE --timeout=300s
```

### Connection from Applications

```python
from pymilvus import connections

# Local
connections.connect(host="localhost", port="19530")

# OpenShift (internal) - replace <namespace> with your namespace
connections.connect(host="milvus.<namespace>.svc.cluster.local", port="19530")
```

## Usage Example

```python
from pymilvus import Collection, FieldSchema, CollectionSchema, DataType

# Define schema
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]
schema = CollectionSchema(fields, description="Document chunks")

# Create collection
collection = Collection("documents", schema)

# Create index
collection.create_index(
    field_name="embedding",
    index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 256}}
)

# Search
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=10
)
```

## Notes

- Data persists in `./data/milvus` and `./data/minio` directories
- For production, configure authentication and TLS
- Milvus v2.4+ required for hybrid search with BM25
