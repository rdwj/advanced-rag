#!/usr/bin/env bash
set -euo pipefail

# Simple Podman helper to run Milvus + MinIO in a pod.

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

POD_NAME="${POD_NAME:-milvus-pod}"
MINIO_NAME="${MINIO_NAME:-milvus-minio}"
MILVUS_NAME="${MILVUS_NAME:-milvus-standalone}"

MINIO_IMAGE="${MINIO_IMAGE:-quay.io/minio/minio}"
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc}"
MILVUS_IMAGE="${MILVUS_IMAGE:-milvusdb/milvus:v2.4.4}"

BUCKET_NAME="${BUCKET_NAME:-a-bucket}"

MINIO_DATA_DIR="${MINIO_DATA_DIR:-${BASE_DIR}/data/minio}"
MILVUS_DATA_DIR="${MILVUS_DATA_DIR:-${BASE_DIR}/data/milvus}"

MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9090}"
MILVUS_GRPC_PORT="${MILVUS_GRPC_PORT:-19530}"
MILVUS_METRICS_PORT="${MILVUS_METRICS_PORT:-9091}"

MINIO_ENDPOINT="127.0.0.1:${MINIO_PORT}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [start|stop|status|destroy|logs|health]
  start    Ensure pod + containers up (creates pod, MinIO, bucket, Milvus)
  stop     Stop the pod (containers keep data)
  status   Show pod and container status
  destroy  Remove pod and containers (data stays under ./data)
  logs     Follow Milvus logs
  health   Query Milvus health endpoint once

Env overrides: POD_NAME, MILVUS_IMAGE, MINIO_IMAGE, MC_IMAGE, BUCKET_NAME,
               MINIO_DATA_DIR, MILVUS_DATA_DIR,
               MILVUS_GRPC_PORT, MILVUS_METRICS_PORT, MINIO_PORT, MINIO_CONSOLE_PORT.
EOF
}

pod_exists() {
  podman pod exists "$POD_NAME"
}

container_exists() {
  podman container exists "$1"
}

container_running() {
  podman ps --format '{{.Names}}' | grep -w "$1" >/dev/null 2>&1
}

ensure_pod() {
  if pod_exists; then
    return
  fi

  podman pod create --name "$POD_NAME" \
    -p "${MILVUS_GRPC_PORT}:19530" \
    -p "${MILVUS_METRICS_PORT}:9091" \
    -p "${MINIO_PORT}:9000" \
    -p "${MINIO_CONSOLE_PORT}:9090"
}

start_minio() {
  mkdir -p "$MINIO_DATA_DIR"

  if container_running "$MINIO_NAME"; then
    return
  fi

  if container_exists "$MINIO_NAME"; then
    podman start "$MINIO_NAME" >/dev/null
    return
  fi

  podman run -d --name "$MINIO_NAME" --pod "$POD_NAME" \
    -v "${MINIO_DATA_DIR}:/data" \
    -e MINIO_ROOT_USER=minioadmin \
    -e MINIO_ROOT_PASSWORD=minioadmin \
    "$MINIO_IMAGE" server /data --console-address ":9090" --address ":9000"
}

ensure_bucket() {
  podman run --rm --pod "$POD_NAME" \
    -e "MC_HOST_local=http://minioadmin:minioadmin@${MINIO_ENDPOINT}" \
    "$MC_IMAGE" mb --ignore-existing "local/${BUCKET_NAME}" >/dev/null
}

start_milvus() {
  mkdir -p "$MILVUS_DATA_DIR"

  if container_running "$MILVUS_NAME"; then
    return
  fi

  if container_exists "$MILVUS_NAME"; then
    podman start "$MILVUS_NAME" >/dev/null
    return
  fi

  podman run -d --name "$MILVUS_NAME" --pod "$POD_NAME" \
    -v "${MILVUS_DATA_DIR}:/var/lib/milvus" \
    -e ETCD_USE_EMBED=true \
    "$MILVUS_IMAGE" \
    milvus run standalone
}

health() {
  curl -fsS "http://127.0.0.1:${MILVUS_METRICS_PORT}/healthz"
}

wait_health() {
  echo "Waiting for Milvus health..."
  for _ in {1..30}; do
    if health >/dev/null 2>&1; then
      echo "Milvus healthy on http://localhost:${MILVUS_METRICS_PORT}/healthz"
      return 0
    fi
    sleep 2
  done

  echo "Milvus did not report healthy (check logs)." >&2
  return 1
}

start() {
  ensure_pod
  start_minio
  ensure_bucket
  start_milvus
  wait_health
}

stop() {
  if pod_exists; then
    podman pod stop "$POD_NAME"
  fi
}

status() {
  podman pod ps --filter "name=${POD_NAME}"
  podman ps --pod "$POD_NAME" 2>/dev/null || true
}

destroy() {
  if pod_exists; then
    podman pod rm -f "$POD_NAME"
  fi
}

logs() {
  if container_exists "$MILVUS_NAME"; then
    podman logs -f "$MILVUS_NAME"
  else
    echo "Milvus container not found" >&2
    return 1
  fi
}

cmd="${1:-help}"
case "$cmd" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  destroy) destroy ;;
  logs) logs ;;
  health) health ;;
  help|--help|-h) usage ;;
  *) usage; exit 1 ;;
esac
