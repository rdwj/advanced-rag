#!/bin/bash
# Redis local development helper script
# Uses Podman to run Redis container

set -e

CONTAINER_NAME="${REDIS_CONTAINER_NAME:-redis-dev}"
REDIS_IMAGE="${REDIS_IMAGE:-docker.io/bitnami/redis:latest}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-dev-redis-password}"
DATA_DIR="${REDIS_DATA_DIR:-$(dirname "$0")/data}"

usage() {
    echo "Usage: $0 {start|stop|status|logs|destroy|cli}"
    echo ""
    echo "Commands:"
    echo "  start    Start Redis container"
    echo "  stop     Stop Redis container"
    echo "  status   Show container status"
    echo "  logs     Show container logs"
    echo "  destroy  Stop and remove container (keeps data)"
    echo "  cli      Open Redis CLI"
    echo ""
    echo "Environment variables:"
    echo "  REDIS_PORT      Port to expose (default: 6379)"
    echo "  REDIS_PASSWORD  Redis password (default: dev-redis-password)"
    echo "  REDIS_DATA_DIR  Data directory (default: ./data)"
    exit 1
}

start() {
    # Create data directory
    mkdir -p "$DATA_DIR"

    # Check if already running
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Redis is already running on port $REDIS_PORT"
        return 0
    fi

    # Check if container exists but stopped
    if podman ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Starting existing container..."
        podman start "$CONTAINER_NAME"
    else
        echo "Creating new Redis container..."
        podman run -d \
            --name "$CONTAINER_NAME" \
            -p "${REDIS_PORT}:6379" \
            -e "REDIS_PASSWORD=${REDIS_PASSWORD}" \
            -e "REDIS_AOF_ENABLED=yes" \
            -v "${DATA_DIR}:/bitnami/redis/data:Z" \
            "$REDIS_IMAGE"
    fi

    echo "Waiting for Redis to be ready..."
    for i in {1..30}; do
        if podman exec "$CONTAINER_NAME" redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG; then
            echo "Redis is ready on port $REDIS_PORT"
            echo "Password: $REDIS_PASSWORD"
            echo "Connect: redis-cli -h localhost -p $REDIS_PORT -a $REDIS_PASSWORD"
            return 0
        fi
        sleep 1
    done
    echo "Warning: Redis may not be fully ready yet"
}

stop() {
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Stopping Redis..."
        podman stop "$CONTAINER_NAME"
        echo "Redis stopped"
    else
        echo "Redis is not running"
    fi
}

status() {
    echo "=== Redis Status ==="
    if podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Status: Running"
        echo "Port: $REDIS_PORT"
        echo "Data: $DATA_DIR"
        echo ""
        echo "Connection test:"
        podman exec "$CONTAINER_NAME" redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null || echo "Failed"
    else
        echo "Status: Stopped"
    fi
}

logs() {
    podman logs -f "$CONTAINER_NAME"
}

destroy() {
    echo "Stopping and removing Redis container..."
    podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container removed (data preserved in $DATA_DIR)"
}

cli() {
    if ! podman ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Redis is not running. Start it first with: $0 start"
        exit 1
    fi
    podman exec -it "$CONTAINER_NAME" redis-cli -a "$REDIS_PASSWORD"
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
