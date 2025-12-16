#!/bin/bash
# Deploy Pyannote Speaker Diarization Server to OpenShift
#
# Prerequisites:
#   - Logged into OpenShift cluster
#   - GPU nodes available
#   - HuggingFace token secret created (pyannote-hf-token)
#
# Usage:
#   ./deploy.sh [namespace] [image] [pull-secret]

set -e

NAMESPACE="${1:-models}"
IMAGE="${2:-quay.io/wjackson/pyannote:latest}"
PULL_SECRET="${3:-pyannote-pull-secret}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying Pyannote server"
echo "  Namespace: $NAMESPACE"
echo "  Image: $IMAGE"
echo "  Pull Secret: $PULL_SECRET"
echo ""

# Ensure namespace exists
oc get namespace "$NAMESPACE" >/dev/null 2>&1 || {
    echo "Creating namespace $NAMESPACE..."
    oc apply -f "$SCRIPT_DIR/manifests/namespace.yaml"
}

# Check for HuggingFace token secret
if ! oc get secret pyannote-hf-token -n "$NAMESPACE" >/dev/null 2>&1; then
    echo ""
    echo "WARNING: HuggingFace token secret not found!"
    echo "Create it with:"
    echo "  oc create secret generic pyannote-hf-token --from-literal=token=hf_xxx -n $NAMESPACE"
    echo ""
    echo "Or use: HF_TOKEN=hf_xxx make create-secret NAMESPACE=$NAMESPACE"
    echo ""
    read -p "Continue without secret? The pod will fail to load the model. [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if pull secret exists (optional)
if ! oc get secret "$PULL_SECRET" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Note: Pull secret '$PULL_SECRET' not found. Deployment will use default credentials."
    PULL_SECRET=""
fi

# Apply PVC if it doesn't exist
if ! oc get pvc pyannote-models -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Creating PVC for model storage..."
    oc apply -f "$SCRIPT_DIR/manifests/pvc.yaml" -n "$NAMESPACE"
fi

# Generate deployment with variable substitution
echo "Deploying pyannote-server..."
cat "$SCRIPT_DIR/manifests/deployment.yaml" | \
    sed "s|IMAGE_PLACEHOLDER|$IMAGE|g" | \
    sed "s|PULL_SECRET_PLACEHOLDER|$PULL_SECRET|g" | \
    oc apply -n "$NAMESPACE" -f -

# Wait for deployment
echo ""
echo "Waiting for deployment to be ready (this may take several minutes)..."
echo "  - Image pull: ~2-5 minutes (14GB image)"
echo "  - Model loading: ~1-2 minutes"
echo ""

if ! oc rollout status deployment/pyannote-server -n "$NAMESPACE" --timeout=600s; then
    echo ""
    echo "Timeout waiting for deployment. Check status with:"
    echo "  oc get pods -l app=pyannote-server -n $NAMESPACE"
    echo "  oc logs -l app=pyannote-server -n $NAMESPACE"
    echo ""
    echo "Common issues:"
    echo "  - GPU nodes not available"
    echo "  - HuggingFace token missing or invalid"
    echo "  - Image pull failures (check pull secret)"
    exit 1
fi

# Get endpoint URL
ROUTE_HOST=$(oc get route pyannote-server -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "$ROUTE_HOST" ]; then
    ENDPOINT="https://$ROUTE_HOST"
    echo ""
    echo "Pyannote server deployed successfully!"
    echo ""
    echo "Endpoint: $ENDPOINT"
    echo ""
    echo "Test with:"
    echo "  curl -sk $ENDPOINT/health"
    echo ""
    echo "Diarize audio:"
    echo "  curl -sk $ENDPOINT/v1/diarize -F 'file=@audio.wav'"
else
    echo ""
    echo "Pyannote server deployed but route not found."
    echo "Check: oc get route pyannote-server -n $NAMESPACE"
fi
