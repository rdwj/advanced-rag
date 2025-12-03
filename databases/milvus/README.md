# Milvus Local (Podman)

Podman-based Milvus + MinIO bundle for local development. Uses embedded etcd, stores data under `./data`, and exposes:
- Milvus gRPC: `localhost:19530`
- Milvus health/metrics: `localhost:9091`
- MinIO API: `localhost:9000` (creds: `minioadmin/minioadmin`)
- MinIO console: `localhost:9090`

## Quick start
```bash
cd /Users/wesjackson/Code/milvus
./podman_milvus.sh start
curl -s http://localhost:9091/healthz   # expect OK
```

## Common commands
- Start / ensure pod up: `./podman_milvus.sh start`
- Health check only: `./podman_milvus.sh health`
- Logs (Milvus): `./podman_milvus.sh logs`
- Stop all containers: `./podman_milvus.sh stop`
- Status summary: `./podman_milvus.sh status`
- Tear down pod/containers: `./podman_milvus.sh destroy` (data stays in `./data`)

## What the helper does
- Creates `milvus-pod` with the needed port mappings.
- Runs MinIO (`milvus-minio`) with data in `./data/minio` and ensures bucket `a-bucket` via `mc`.
- Runs Milvus (`milvus-standalone`, image `milvusdb/milvus:v2.4.4`) with embedded etcd and data in `./data/milvus`.

### Customizing
You can override defaults via env vars before running the script:
`POD_NAME`, `MILVUS_IMAGE`, `MINIO_IMAGE`, `MC_IMAGE`, `BUCKET_NAME`, `MILVUS_DATA_DIR`, `MINIO_DATA_DIR`, `MILVUS_GRPC_PORT`, `MILVUS_METRICS_PORT`, `MINIO_PORT`, `MINIO_CONSOLE_PORT`.

### Notes
- Existing data from the previous setup was copied into `./data/milvus` and `./data/minio`.
- If ports are in use, stop other Milvus/MinIO pods first (`podman pod stop milvus-pod`).
