#!/bin/bash
# Deploy GPT-OSS 20B model to OpenShift
#
# Prerequisites:
#   - Logged into OpenShift cluster
#   - gpt-oss namespace exists with GPU nodes available
#   - Model files already uploaded to S3 (see scripts/stream_to_s3.py)
#   - Data connection secret exists (aws-connection-model-storage)
#
# Usage:
#   ./deploy.sh [namespace]

set -e

NAMESPACE="${1:-gpt-oss}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying GPT-OSS 20B to namespace: $NAMESPACE"

# Ensure namespace exists
oc get namespace "$NAMESPACE" >/dev/null 2>&1 || {
    echo "Creating namespace $NAMESPACE..."
    oc new-project "$NAMESPACE"
}

# Check for data connection secret
if ! oc get secret aws-connection-model-storage -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Data connection secret 'aws-connection-model-storage' not found."
    echo "Creating from template..."
    oc apply -f "$SCRIPT_DIR/manifests/data-connection-secret.yaml" -n "$NAMESPACE"
    echo "WARNING: Please update the secret with your actual S3 credentials!"
    echo "  oc edit secret aws-connection-model-storage -n $NAMESPACE"
fi

# Deploy ServingRuntime
echo "Deploying ServingRuntime..."
oc apply -f "$SCRIPT_DIR/manifests/serving-runtime.yaml" -n "$NAMESPACE"

# Wait for ServingRuntime to be recognized
sleep 2

# Deploy InferenceService
echo "Deploying InferenceService..."
oc apply -f "$SCRIPT_DIR/manifests/inference-service-s3.yaml" -n "$NAMESPACE"

# Wait for deployment (this can take a while for large models)
echo "Waiting for deployment to be ready (this may take several minutes for GPU scheduling)..."
if ! oc wait --for=condition=Ready inferenceservice/gpt-oss-20b-rhaiis -n "$NAMESPACE" --timeout=600s; then
    echo ""
    echo "Timeout waiting for InferenceService. Check pod status:"
    echo "  oc get pods -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -n $NAMESPACE"
    echo ""
    echo "Check pod logs:"
    echo "  oc logs -l serving.kserve.io/inferenceservice=gpt-oss-20b-rhaiis -n $NAMESPACE"
    echo ""
    echo "Common issues:"
    echo "  - GPU nodes not available or all in use"
    echo "  - Model files not found in S3 path: gpt-oss-models/gpt-oss-20b"
    echo "  - S3 credentials incorrect in aws-connection-model-storage secret"
    exit 1
fi

# Get endpoint URL
ROUTE_HOST=$(oc get route gpt-oss-20b-rhaiis -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -z "$ROUTE_HOST" ]; then
    # Try to get the internal URL from InferenceService
    INTERNAL_URL=$(oc get inferenceservice gpt-oss-20b-rhaiis -n "$NAMESPACE" -o jsonpath='{.status.url}' 2>/dev/null || echo "")
    if [ -n "$INTERNAL_URL" ]; then
        echo ""
        echo "GPT-OSS 20B deployed successfully!"
        echo "Internal endpoint: $INTERNAL_URL"
        echo ""
        echo "Note: No external route found. Create one with:"
        echo "  oc expose svc/gpt-oss-20b-rhaiis-predictor -n $NAMESPACE"
    fi
else
    ENDPOINT="https://$ROUTE_HOST"
    echo ""
    echo "GPT-OSS 20B deployed successfully!"
    echo "External endpoint: $ENDPOINT"
    echo ""
    echo "Test with:"
    echo "  curl -sk -X POST $ENDPOINT/v1/chat/completions \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"model\": \"gpt-oss-20b-rhaiis\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
fi
