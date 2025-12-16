#!/bin/bash
# Valkey local development helper script
# Uses Podman to run Valkey container

set -e

CONTAINER_NAME="${VALKEY_CONTAINER_NAME:-valkey-dev}"
VALKEY_IMAGE="${VALKEY_IMAGE:-docker.io/bitnami/valkey:latest}"
VALKEY_PORT="${VALKEY_PORT:-6379}"
VALKEY_PASSWORD="${VALKEY_PASSWORD:-dev-valkey-password}"
DATA_DIR="${VALKEY_DATA_DIR:-$(dirname "$0")/data}"

usage() {
    echo "Usage: $0 {start|stop|status|logs|destroy|cli}"
    echo ""
    echo "Commands:"
    echo "  start    Start Valkey container"
    echo "  stop     Stop Valkey container"
    echo "  status   Show container status"
    echo "  logs     Show container logs"
    echo "  destroy  Stop and remove container (keeps data)"
    echo "  cli      Open Valkey CLI"
    echo ""
    echo "Environment variables:"
    echo "  VALKEY_PORT      Port to expose (default: 6379)"
    echo "  VALKEY_PASSWORD  Valkey password (default: dev-valkey-password)"
    echo "  VALKEY_DATA_DIR  Data directory (default: ./data)"
    exit 1
}

start() {
    # Create data directory
    mkdir -p "$DATA_DIR"

    # Check if already running
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Valkey is already running on port $VALKEY_PORT"
        return 0
    fi

    # Check if container exists but stopped
    if podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Starting existing container..."
        podman start "$CONTAINER_NAME"
    else
        echo "Creating new Valkey container..."
        podman run -d \
            --name "$CONTAINER_NAME" \
            -p "${VALKEY_PORT}:6379" \
            -e "VALKEY_PASSWORD=${VALKEY_PASSWORD}" \
            -e "VALKEY_AOF_ENABLED=yes" \
            -v "${DATA_DIR}:/bitnami/valkey/data:Z" \
            "$VALKEY_IMAGE"
    fi

    echo "Waiting for Valkey to be ready..."
    for i in {1..30}; do
        if podman exec "$CONTAINER_NAME" valkey-cli -a "$VALKEY_PASSWORD" ping 2>/dev/null | grep -q PONG; then
            echo "Valkey is ready on port $VALKEY_PORT"
            echo "Password: $VALKEY_PASSWORD"
            echo "Connect: valkey-cli -h localhost -p $VALKEY_PORT -a $VALKEY_PASSWORD"
            echo "   (or): redis-cli -h localhost -p $VALKEY_PORT -a $VALKEY_PASSWORD"
            return 0
        fi
        sleep 1
    done
    echo "Warning: Valkey may not be fully ready yet"
}

stop() {
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Stopping Valkey..."
        podman stop "$CONTAINER_NAME"
        echo "Valkey stopped"
    else
        echo "Valkey is not running"
    fi
}

status() {
    echo "=== Valkey Status ==="
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Status: Running"
        echo "Port: $VALKEY_PORT"
        echo "Data: $DATA_DIR"
        echo ""
        echo "Connection test:"
        podman exec "$CONTAINER_NAME" valkey-cli -a "$VALKEY_PASSWORD" ping 2>/dev/null || echo "Failed"
    else
        echo "Status: Stopped"
    fi
}

logs() {
    podman logs -f "$CONTAINER_NAME"
}

destroy() {
    echo "Stopping and removing Valkey container..."
    podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container removed (data preserved in $DATA_DIR)"
}

cli() {
    if ! podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Valkey is not running. Start it first with: $0 start"
        exit 1
    fi
    podman exec -it "$CONTAINER_NAME" valkey-cli -a "$VALKEY_PASSWORD"
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    status)  status ;;
    logs)    logs ;;
    destroy) destroy ;;
    cli)     cli ;;
    *)       usage ;;
esac
