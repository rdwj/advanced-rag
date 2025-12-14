#!/bin/bash
# Deploy Whisper Speech-to-Text model to OpenShift AI
#
# Prerequisites:
#   - Logged into OpenShift cluster
#   - GPU nodes available
#   - RHAIIS registry access configured
#
# Usage:
#   ./deploy.sh [namespace]

set -e

NAMESPACE="${1:-models}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying Whisper model to namespace: $NAMESPACE"

# Ensure namespace exists
oc get namespace "$NAMESPACE" >/dev/null 2>&1 || {
    echo "Creating namespace $NAMESPACE..."
    oc apply -f "$SCRIPT_DIR/manifests/namespace.yaml"
}

# Deploy ServingRuntime
echo "Deploying ServingRuntime..."
oc apply -f "$SCRIPT_DIR/manifests/serving-runtime.yaml" -n "$NAMESPACE"

# Wait for ServingRuntime to be recognized
sleep 2

# Deploy InferenceService
echo "Deploying InferenceService..."
oc apply -f "$SCRIPT_DIR/manifests/inference-service.yaml" -n "$NAMESPACE"

# Wait for deployment (this can take a while for GPU scheduling)
echo "Waiting for deployment to be ready (this may take several minutes for GPU scheduling)..."
if ! oc wait --for=condition=Ready inferenceservice/whisper-large-fp8 -n "$NAMESPACE" --timeout=300s; then
    echo ""
    echo "Timeout waiting for InferenceService. Check pod status:"
    echo "  oc get pods -l serving.kserve.io/inferenceservice=whisper-large-fp8 -n $NAMESPACE"
    echo ""
    echo "Check pod logs:"
    echo "  oc logs -l serving.kserve.io/inferenceservice=whisper-large-fp8 -n $NAMESPACE -c kserve-container"
    echo ""
    echo "Common issues:"
    echo "  - GPU nodes not available or all in use"
    echo "  - vLLM version doesn't support Whisper (need RHAIIS 3.2.4+)"
    echo "  - Wrong --limit-mm-per-prompt format for vLLM version"
    exit 1
fi

# Get endpoint URL
ROUTE_HOST=$(oc get route whisper-large-fp8 -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -z "$ROUTE_HOST" ]; then
    INTERNAL_URL=$(oc get inferenceservice whisper-large-fp8 -n "$NAMESPACE" -o jsonpath='{.status.url}' 2>/dev/null || echo "")
    if [ -n "$INTERNAL_URL" ]; then
        echo ""
        echo "Whisper deployed successfully!"
        echo "Internal endpoint: $INTERNAL_URL"
    fi
else
    ENDPOINT="https://$ROUTE_HOST"
    echo ""
    echo "Whisper deployed successfully!"
    echo "External endpoint: $ENDPOINT"
    echo ""
    echo "Test transcription with:"
    echo "  curl -sk $ENDPOINT/v1/audio/transcriptions \\"
    echo "    -F file=@audio.wav \\"
    echo "    -F model=whisper-large-fp8"
fi
