#!/bin/bash
# Deploy Granite Embedding 278M model to OpenShift
#
# Prerequisites:
#   - Logged into OpenShift cluster
#   - caikit-embeddings namespace exists
#   - Model bootstrapped and uploaded to S3 (see scripts/bootstrap_embedding_model.py)
#
# Usage:
#   ./deploy-granite-embedding.sh [namespace]

set -e

NAMESPACE="${1:-caikit-embeddings}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying Granite Embedding 278M to namespace: $NAMESPACE"

# Ensure namespace exists
oc get namespace "$NAMESPACE" >/dev/null 2>&1 || {
    echo "Error: Namespace $NAMESPACE does not exist"
    exit 1
}

# Deploy ServingRuntime if not present
if ! oc get servingruntime caikit-standalone-runtime -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Deploying ServingRuntime..."
    oc apply -f "$SCRIPT_DIR/manifests/base/serving-runtime.yaml" -n "$NAMESPACE"
fi

# Check for data connection secret
if ! oc get secret aws-connection-model-storage -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "Warning: Data connection secret 'aws-connection-model-storage' not found."
    echo "Please create the secret or apply manifests/base/data-connection-secret.yaml"
    exit 1
fi

# Deploy InferenceService
echo "Deploying InferenceService..."
oc apply -f "$SCRIPT_DIR/manifests/granite-embedding/inference-service.yaml" -n "$NAMESPACE"

# Wait for deployment
echo "Waiting for deployment to be ready..."
oc wait --for=condition=Ready inferenceservice/granite-embedding-278m -n "$NAMESPACE" --timeout=300s || {
    echo "Timeout waiting for InferenceService. Check pod logs:"
    echo "  oc logs -l serving.kserve.io/inferenceservice=granite-embedding-278m -n $NAMESPACE"
    exit 1
}

# Deploy Service and Route for external access
echo "Creating external route..."
oc apply -f "$SCRIPT_DIR/manifests/granite-embedding/service.yaml" -n "$NAMESPACE"
oc apply -f "$SCRIPT_DIR/manifests/granite-embedding/route.yaml" -n "$NAMESPACE"

# Get external endpoint
ROUTE_HOST=$(oc get route granite-embedding-278m -n "$NAMESPACE" -o jsonpath='{.spec.host}')
ENDPOINT="https://$ROUTE_HOST"
echo ""
echo "Granite Embedding 278M deployed successfully!"
echo "External endpoint: $ENDPOINT"
echo ""
echo "Test with:"
echo "  curl -sk -X POST $ENDPOINT/api/v1/task/embedding \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model_id\": \"granite-embedding-278m\", \"inputs\": \"Hello world\"}'"
