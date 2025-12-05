# Makefile for Advanced RAG Kustomize Deployments
#
# Usage:
#   make deploy                    # Deploy dev overlay to advanced-rag namespace
#   make deploy OVERLAY=dev        # Same as above
#   make deploy OVERLAY=example-customer NAMESPACE=customer-rag
#   make build                     # Preview what would be deployed
#   make diff                      # Show diff between deployed and local
#
# Prerequisites:
#   - oc login to OpenShift cluster
#   - Secrets created in target namespace (see overlays/*/secrets.yaml)

SHELL := /bin/bash

# Configuration
OVERLAY ?= dev
NAMESPACE ?= advanced-rag
MANIFESTS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: help build deploy diff rollout status clean

help:
	@echo "Advanced RAG Kustomize Deployment"
	@echo ""
	@echo "Usage:"
	@echo "  make deploy                    Deploy dev overlay"
	@echo "  make deploy OVERLAY=<name>     Deploy specific overlay"
	@echo "  make build                     Preview manifests (dry-run)"
	@echo "  make diff                      Show diff vs deployed"
	@echo "  make rollout                   Restart all deployments"
	@echo "  make status                    Check service health"
	@echo "  make clean                     Delete all resources"
	@echo ""
	@echo "Available overlays:"
	@ls -1 overlays/
	@echo ""
	@echo "Environment Variables:"
	@echo "  OVERLAY    - Overlay to deploy (default: dev)"
	@echo "  NAMESPACE  - Target namespace (default: advanced-rag)"

build:
	@echo "Building manifests for overlay: $(OVERLAY)"
	@kubectl kustomize overlays/$(OVERLAY)

deploy: check-prereqs
	@echo "Deploying overlay '$(OVERLAY)' to namespace '$(NAMESPACE)'"
	@oc apply -k overlays/$(OVERLAY) -n $(NAMESPACE)
	@echo ""
	@echo "Waiting for rollouts..."
	@oc rollout status deployment/chunker-service -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/embedding-service -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/plan-service -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/evaluator-service -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/rerank-service -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/vector-gateway -n $(NAMESPACE) --timeout=120s || true
	@oc rollout status deployment/retrieval-mcp -n $(NAMESPACE) --timeout=120s || true
	@echo ""
	@$(MAKE) status

diff:
	@echo "Diff for overlay '$(OVERLAY)' vs deployed in '$(NAMESPACE)'"
	@oc diff -k overlays/$(OVERLAY) -n $(NAMESPACE) || true

rollout:
	@echo "Restarting all deployments in $(NAMESPACE)"
	@oc rollout restart deployment/chunker-service -n $(NAMESPACE)
	@oc rollout restart deployment/embedding-service -n $(NAMESPACE)
	@oc rollout restart deployment/plan-service -n $(NAMESPACE)
	@oc rollout restart deployment/evaluator-service -n $(NAMESPACE)
	@oc rollout restart deployment/rerank-service -n $(NAMESPACE)
	@oc rollout restart deployment/vector-gateway -n $(NAMESPACE)
	@oc rollout restart deployment/retrieval-mcp -n $(NAMESPACE)
	@echo "Waiting for rollouts..."
	@oc rollout status deployment -l app.kubernetes.io/part-of=advanced-rag -n $(NAMESPACE) --timeout=300s

status:
	@echo "Service Health Status ($(NAMESPACE)):"
	@echo "======================================="
	@CLUSTER_DOMAIN=$$(oc get ingresses.config/cluster -o jsonpath='{.spec.domain}' 2>/dev/null); \
	printf "%-20s %s\n" "chunker-service:" "$$(curl -sk https://chunker-service-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "embedding-service:" "$$(curl -sk https://embedding-service-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "plan-service:" "$$(curl -sk https://plan-service-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "evaluator-service:" "$$(curl -sk https://evaluator-service-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "rerank-service:" "$$(curl -sk https://rerank-service-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "vector-gateway:" "$$(curl -sk https://vector-gateway-$(NAMESPACE).$$CLUSTER_DOMAIN/healthz 2>/dev/null || echo 'UNREACHABLE')"; \
	printf "%-20s %s\n" "retrieval-mcp:" "$$(curl -sk https://retrieval-mcp-$(NAMESPACE).$$CLUSTER_DOMAIN/mcp/ 2>/dev/null | head -c 50 || echo 'UNREACHABLE')"

pods:
	@oc get pods -n $(NAMESPACE) -l app.kubernetes.io/part-of=advanced-rag

logs-%:
	@oc logs -f deployment/$* -n $(NAMESPACE)

clean:
	@echo "Removing all resources from $(NAMESPACE)"
	@oc delete -k overlays/$(OVERLAY) -n $(NAMESPACE) --ignore-not-found=true

check-prereqs:
	@oc whoami > /dev/null 2>&1 || (echo "ERROR: Not logged into OpenShift. Run 'oc login' first." && exit 1)
	@oc get namespace $(NAMESPACE) > /dev/null 2>&1 || (echo "Creating namespace $(NAMESPACE)" && oc new-project $(NAMESPACE))
