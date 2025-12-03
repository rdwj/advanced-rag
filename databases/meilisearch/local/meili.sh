#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-start}"

# Determine script directory for portable paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${SCRIPT_DIR}"
DATA_DIR="${BASE_DIR}/data"
LOG_FILE="${BASE_DIR}/meili.log"
PID_FILE="${BASE_DIR}/meili.pid"

CONTAINER_NAME="${CONTAINER_NAME:-meilisearch}"
IMAGE="${MEILI_IMAGE:-getmeili/meilisearch:v1.16}"
MASTER_KEY="${MEILI_MASTER_KEY:-dev-meili-master-key}"

mkdir -p "${DATA_DIR}"

has_podman() {
  command -v podman >/dev/null 2>&1
}

has_docker() {
  command -v docker >/dev/null 2>&1
}

# Prefer podman over docker
get_container_runtime() {
  if has_podman; then
    echo "podman"
  elif has_docker; then
    echo "docker"
  else
    echo ""
  fi
}

start_container() {
  local runtime
  runtime=$(get_container_runtime)
  if [[ -z "${runtime}" ]]; then
    return 1
  fi

  "${runtime}" rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  "${runtime}" run -d \
    --name "${CONTAINER_NAME}" \
    -p 7700:7700 \
    -v "${DATA_DIR}:/meili_data:Z" \
    -e MEILI_MASTER_KEY="${MASTER_KEY}" \
    -e MEILI_ENV=development \
    "${IMAGE}"
  echo "Meilisearch (${runtime}) started as ${CONTAINER_NAME} (master key: ${MASTER_KEY})."
  echo "Data directory: ${DATA_DIR}"
}

stop_container() {
  local runtime
  runtime=$(get_container_runtime)
  if [[ -n "${runtime}" ]]; then
    "${runtime}" stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  fi
}

destroy_container() {
  local runtime
  runtime=$(get_container_runtime)
  if [[ -n "${runtime}" ]]; then
    "${runtime}" stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    "${runtime}" rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  fi
}

download_binary() {
  if [[ ! -f "${BASE_DIR}/meilisearch" ]]; then
    echo "Downloading Meilisearch binary to ${BASE_DIR}..."
    (cd "${BASE_DIR}" && curl -L https://install.meilisearch.com | sh)
  fi
}

start_binary() {
  download_binary
  if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo "Meilisearch already running with PID $(cat "${PID_FILE}")."
    return
  fi
  nohup "${BASE_DIR}/meilisearch" \
    --db-path "${DATA_DIR}" \
    --env development \
    --http-addr "127.0.0.1:7700" \
    --master-key "${MASTER_KEY}" \
    >"${LOG_FILE}" 2>&1 &
  echo $! > "${PID_FILE}"
  echo "Meilisearch (binary) started pid $(cat "${PID_FILE}") (master key: ${MASTER_KEY})."
  echo "Data directory: ${DATA_DIR}"
  echo "Logs: ${LOG_FILE}"
}

stop_binary() {
  if [[ -f "${PID_FILE}" ]]; then
    PID=$(cat "${PID_FILE}")
    if kill -0 "${PID}" 2>/dev/null; then
      kill "${PID}"
      echo "Stopped Meilisearch pid ${PID}"
    fi
    rm -f "${PID_FILE}"
  fi
}

case "${CMD}" in
  start)
    runtime=$(get_container_runtime)
    if [[ -n "${runtime}" ]]; then
      start_container
    else
      start_binary
    fi
    echo ""
    echo "Enable vectorStore once:"
    echo "  curl -X PATCH 'http://localhost:7700/experimental-features/' \\"
    echo "    -H 'Authorization: Bearer ${MASTER_KEY}' \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    --data-binary '{\"vectorStore\": true}'"
    ;;
  stop)
    runtime=$(get_container_runtime)
    if [[ -n "${runtime}" ]]; then
      stop_container
    else
      stop_binary
    fi
    ;;
  destroy)
    runtime=$(get_container_runtime)
    if [[ -n "${runtime}" ]]; then
      destroy_container
    else
      stop_binary
    fi
    # Optionally remove data - uncomment if you want destroy to clear data
    # rm -rf "${DATA_DIR}" "${LOG_FILE}" "${PID_FILE}"
    echo "Container removed. Data preserved in ${DATA_DIR}"
    echo "To remove data: rm -rf ${DATA_DIR}"
    ;;
  status)
    echo "Script directory: ${SCRIPT_DIR}"
    echo "Data directory: ${DATA_DIR}"
    echo "Log file: ${LOG_FILE}"
    echo "PID file: ${PID_FILE}"
    runtime=$(get_container_runtime)
    if [[ -n "${runtime}" ]]; then
      echo "Container runtime: ${runtime}"
      "${runtime}" ps -a --filter name="${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
    elif [[ -f "${PID_FILE}" ]]; then
      PID=$(cat "${PID_FILE}")
      if kill -0 "${PID}" 2>/dev/null; then
        echo "Binary running with PID ${PID}"
      else
        echo "PID file exists but process not running"
      fi
    else
      echo "Meilisearch not running"
    fi
    ;;
  *)
    echo "Usage: $0 [start|stop|destroy|status]"
    echo ""
    echo "Commands:"
    echo "  start   - Start Meilisearch (prefers podman/docker, falls back to binary)"
    echo "  stop    - Stop Meilisearch"
    echo "  destroy - Stop and remove container (data preserved)"
    echo "  status  - Show current status and paths"
    echo ""
    echo "Environment variables:"
    echo "  CONTAINER_NAME  - Container name (default: meilisearch)"
    echo "  MEILI_IMAGE     - Container image (default: getmeili/meilisearch:v1.16)"
    echo "  MEILI_MASTER_KEY - Master key (default: dev-meili-master-key)"
    exit 1
    ;;
esac
