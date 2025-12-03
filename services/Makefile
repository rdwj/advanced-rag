# Services Makefile for Advanced RAG
#
# Deploy all services to OpenShift with: make deploy-all
# Build all services remotely with: make build-all
#
# Prerequisites:
#   - oc login to OpenShift cluster
#   - ssh ec2-dev configured
#   - Secrets already created in advanced-rag namespace
#
# Usage:
#   make build-all        # Build all services on ec2-dev
#   make push-all         # Push all images to OpenShift registry
#   make deploy-all       # Apply manifests and rollout all services
#   make rollout-all      # Just restart all deployments
#   make status           # Check health of all services
#   make build-<service>  # Build a single service (e.g., make build-plan)
#   make deploy-<service> # Deploy a single service

SHELL := /bin/bash

# Configuration
NAMESPACE := advanced-rag
REGISTRY := $(shell oc registry info 2>/dev/null)
TOKEN := $(shell oc whoami -t 2>/dev/null)
REMOTE_HOST := ec2-dev
REMOTE_BUILD_DIR := ~/builds

# Service definitions
# Self-contained services (build from their own directory)
SELF_CONTAINED_SERVICES := chunker plan evaluator

# Services requiring root context (depend on rag_core)
ROOT_CONTEXT_SERVICES := embedding rerank vector-gateway

# All services
ALL_SERVICES := $(SELF_CONTAINED_SERVICES) $(ROOT_CONTEXT_SERVICES)

# Service directory mapping
chunker_DIR := chunker_service
plan_DIR := plan_service
evaluator_DIR := evaluator_service
embedding_DIR := embedding_service
rerank_DIR := rerank_service
vector-gateway_DIR := vector_gateway

# OpenShift deployment names
chunker_DEPLOY := chunker-service
plan_DEPLOY := plan-service
evaluator_DEPLOY := evaluator-service
embedding_DEPLOY := embedding-service
rerank_DEPLOY := rerank-service
vector-gateway_DEPLOY := vector-gateway

# Route hostnames (derived from cluster)
CLUSTER_DOMAIN := $(shell oc get ingresses.config/cluster -o jsonpath='{.spec.domain}' 2>/dev/null)

.PHONY: all help build-all push-all deploy-all rollout-all status login check-prereqs clean

help:
	@echo "Services Makefile for Advanced RAG"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - oc login to OpenShift cluster"
	@echo "  - ssh ec2-dev configured for remote builds"
	@echo "  - Secrets created in $(NAMESPACE) namespace"
	@echo ""
	@echo "Targets:"
	@echo "  make build-all       Build all services on ec2-dev"
	@echo "  make push-all        Push all images to OpenShift registry"
	@echo "  make deploy-all      Apply manifests and rollout all services"
	@echo "  make rollout-all     Restart all deployments (use existing images)"
	@echo "  make status          Check health of all services"
	@echo ""
	@echo "Single service targets:"
	@echo "  make build-<svc>     Build one service (plan, embedding, etc.)"
	@echo "  make push-<svc>      Push one service image"
	@echo "  make deploy-<svc>    Deploy one service"
	@echo "  make rollout-<svc>   Restart one deployment"
	@echo ""
	@echo "Services: $(ALL_SERVICES)"

check-prereqs:
	@echo "Checking prerequisites..."
	@oc whoami > /dev/null 2>&1 || (echo "ERROR: Not logged into OpenShift. Run 'oc login' first." && exit 1)
	@ssh -q $(REMOTE_HOST) exit || (echo "ERROR: Cannot connect to $(REMOTE_HOST). Check SSH config." && exit 1)
	@echo "Prerequisites OK"

login:
	@echo "Logging into OpenShift registry on $(REMOTE_HOST)..."
	@ssh $(REMOTE_HOST) "podman login --tls-verify=false -u unused -p '$(TOKEN)' '$(REGISTRY)'" 2>&1

# ============================================================================
# Build targets
# ============================================================================

build-all: check-prereqs login $(addprefix build-,$(ALL_SERVICES))
	@echo "All services built successfully"

# Self-contained services (sync service dir, build from there)
define SELF_CONTAINED_BUILD
build-$(1): check-prereqs
	@echo "Building $(1) service..."
	@rsync -az --delete $$($(1)_DIR)/ $(REMOTE_HOST):$(REMOTE_BUILD_DIR)/$(1)-service/
	@ssh $(REMOTE_HOST) "cd $(REMOTE_BUILD_DIR)/$(1)-service && podman build --platform linux/amd64 -t $(1)-service:latest -f Containerfile . 2>&1" | tail -10
	@echo "$(1) service built"
endef

$(foreach svc,$(SELF_CONTAINED_SERVICES),$(eval $(call SELF_CONTAINED_BUILD,$(svc))))

# Root context services (sync rag_core + service, build from services context)
define ROOT_CONTEXT_BUILD
build-$(1): check-prereqs
	@echo "Building $(1) service..."
	@ssh $(REMOTE_HOST) "mkdir -p $(REMOTE_BUILD_DIR)/$(1)-service"
	@rsync -az --delete rag_core/ $(REMOTE_HOST):$(REMOTE_BUILD_DIR)/$(1)-service/rag_core/
	@rsync -az --delete $$($(1)_DIR)/ $(REMOTE_HOST):$(REMOTE_BUILD_DIR)/$(1)-service/$$($(1)_DIR)/
	@ssh $(REMOTE_HOST) "cd $(REMOTE_BUILD_DIR)/$(1)-service && podman build --platform linux/amd64 -t $(1)-service:latest -f $$($(1)_DIR)/Containerfile . 2>&1" | tail -10
	@echo "$(1) service built"
endef

$(foreach svc,$(ROOT_CONTEXT_SERVICES),$(eval $(call ROOT_CONTEXT_BUILD,$(svc))))

# ============================================================================
# Push targets
# ============================================================================

push-all: login $(addprefix push-,$(ALL_SERVICES))
	@echo "All images pushed successfully"

define PUSH_TARGET
push-$(1): login
	@echo "Pushing $(1) service..."
	@ssh $(REMOTE_HOST) "podman tag $(1)-service:latest $(REGISTRY)/$(NAMESPACE)/$(1)-service:latest 2>/dev/null || true"
	@ssh $(REMOTE_HOST) "podman push --tls-verify=false $(REGISTRY)/$(NAMESPACE)/$(1)-service:latest 2>&1" | tail -5
	@echo "$(1) service pushed"
endef

$(foreach svc,$(ALL_SERVICES),$(eval $(call PUSH_TARGET,$(svc))))

# ============================================================================
# Deploy targets
# ============================================================================

deploy-all: $(addprefix deploy-,$(ALL_SERVICES))
	@echo "All services deployed"
	@$(MAKE) status

define DEPLOY_TARGET
deploy-$(1):
	@echo "Deploying $(1) service..."
	@oc apply -f $$($(1)_DIR)/manifests/ -n $(NAMESPACE)
	@oc rollout restart deployment/$$($(1)_DEPLOY) -n $(NAMESPACE) 2>/dev/null || true
	@oc rollout status deployment/$$($(1)_DEPLOY) -n $(NAMESPACE) --timeout=120s
	@echo "$(1) service deployed"
endef

$(foreach svc,$(ALL_SERVICES),$(eval $(call DEPLOY_TARGET,$(svc))))

# ============================================================================
# Rollout targets (restart without rebuilding)
# ============================================================================

rollout-all: $(addprefix rollout-,$(ALL_SERVICES))
	@echo "All services restarted"
	@$(MAKE) status

define ROLLOUT_TARGET
rollout-$(1):
	@echo "Restarting $(1) service..."
	@oc rollout restart deployment/$$($(1)_DEPLOY) -n $(NAMESPACE)
	@oc rollout status deployment/$$($(1)_DEPLOY) -n $(NAMESPACE) --timeout=120s
endef

$(foreach svc,$(ALL_SERVICES),$(eval $(call ROLLOUT_TARGET,$(svc))))

# ============================================================================
# Status and health checks
# ============================================================================

status:
	@echo "Service Health Status:"
	@echo "====================="
	@printf "%-20s %s\n" "chunker-service:" "$$(curl -sk https://chunker-service-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"
	@printf "%-20s %s\n" "plan-service:" "$$(curl -sk https://plan-service-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"
	@printf "%-20s %s\n" "evaluator-service:" "$$(curl -sk https://evaluator-service-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"
	@printf "%-20s %s\n" "embedding-service:" "$$(curl -sk https://embedding-service-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"
	@printf "%-20s %s\n" "rerank-service:" "$$(curl -sk https://rerank-service-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"
	@printf "%-20s %s\n" "vector-gateway:" "$$(curl -sk https://vector-gateway-$(NAMESPACE).$(CLUSTER_DOMAIN)/healthz 2>/dev/null || echo 'UNREACHABLE')"

pods:
	@oc get pods -n $(NAMESPACE) -l app.kubernetes.io/part-of=advanced-rag

logs-%:
	@oc logs -f deployment/$($*_DEPLOY) -n $(NAMESPACE)

# ============================================================================
# Full pipeline: build, push, deploy
# ============================================================================

all: build-all push-all deploy-all

# Single service full pipeline
%-full: build-% push-% deploy-%
	@echo "$* service fully deployed"

# ============================================================================
# Cleanup
# ============================================================================

clean:
	@echo "Cleaning remote build directories..."
	@ssh $(REMOTE_HOST) "rm -rf $(REMOTE_BUILD_DIR)/*-service" 2>/dev/null || true
	@echo "Clean complete"
