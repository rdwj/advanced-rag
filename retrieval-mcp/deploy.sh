#!/bin/bash
# Deployment script for retrieval-mcp
#
# This script deploys using the centralized Kustomize manifests.
# For full deployment of all services, use: cd ../manifests && make deploy

set -e

PROJECT=${1:-advanced-rag}

echo "========================================="
echo "Retrieval MCP Deployment"
echo "========================================="
echo "Project: $PROJECT"
echo ""

# Check if logged in to OpenShift
if ! oc whoami &>/dev/null; then
    echo "Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

# Check namespace exists
if ! oc get namespace "$PROJECT" &>/dev/null; then
    echo "Creating namespace: $PROJECT"
    oc new-project "$PROJECT"
fi

# Deploy using kustomize from the centralized manifests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="$SCRIPT_DIR/../manifests"

echo "Deploying retrieval-mcp from centralized manifests..."
oc apply -k "$MANIFESTS_DIR/base/retrieval-mcp" -n "$PROJECT"

# Wait for rollout
echo "Waiting for deployment..."
oc rollout status deployment/retrieval-mcp -n "$PROJECT" --timeout=120s

# Get route
ROUTE=$(oc get route retrieval-mcp -n "$PROJECT" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
if [ -n "$ROUTE" ]; then
    echo "MCP Server URL: https://$ROUTE/mcp/"
    echo ""
    echo "Test with MCP Inspector:"
    echo "  npx @modelcontextprotocol/inspector https://$ROUTE/mcp/"
else
    echo "Warning: Could not retrieve route URL"
fi
echo ""
echo "Note: For full stack deployment, use:"
echo "  cd ../manifests && make deploy"
echo "========================================="
