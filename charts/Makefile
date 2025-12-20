# ============================================================================
# Advanced RAG Charts - Makefile
# ============================================================================
# Common tasks for Helm chart development and deployment
# ============================================================================

NAMESPACE ?= advanced-rag
REGISTRY ?= quay.io/your-org

# List of all charts
CHARTS = rag-milvus rag-valkey rag-vllm-embeddings rag-docling rag-services

.PHONY: help lint lint-all template deps package push-all deploy undeploy clean

help:
	@echo "Advanced RAG Helm Charts"
	@echo ""
	@echo "Usage: make <target> [NAMESPACE=xxx]"
	@echo ""
	@echo "Targets:"
	@echo "  lint         - Lint all charts"
	@echo "  template     - Render templates for all charts"
	@echo "  deps         - Update chart dependencies"
	@echo "  package      - Package all charts"
	@echo "  push-all     - Push all charts to registry"
	@echo "  deploy       - Deploy all charts (in order)"
	@echo "  undeploy     - Remove all deployments"
	@echo "  clean        - Clean build artifacts"
	@echo ""
	@echo "Individual chart targets:"
	@echo "  deploy-milvus, deploy-valkey, deploy-embeddings, deploy-docling, deploy-services"
	@echo ""
	@echo "Variables:"
	@echo "  NAMESPACE    - Target namespace (default: advanced-rag)"
	@echo "  REGISTRY     - OCI registry (default: quay.io/your-org)"

# ============================================================================
# Linting
# ============================================================================

lint:
	@echo "=== Linting all charts ==="
	@for chart in $(CHARTS); do \
		echo "--- Linting $$chart ---"; \
		helm lint $$chart || exit 1; \
	done
	@echo "✓ All charts passed linting"

# ============================================================================
# Template Rendering
# ============================================================================

template:
	@echo "=== Rendering templates ==="
	@for chart in $(CHARTS); do \
		echo "--- $$chart ---"; \
		helm template test $$chart > /dev/null && echo "✓ $$chart" || exit 1; \
	done

# ============================================================================
# Dependencies
# ============================================================================

deps:
	@echo "=== Updating dependencies ==="
	helm repo add milvus https://zilliztech.github.io/milvus-helm/ 2>/dev/null || true
	helm repo update
	cd rag-milvus && helm dependency update

# ============================================================================
# Packaging
# ============================================================================

package: lint
	@echo "=== Packaging charts ==="
	@mkdir -p .packages
	@for chart in $(CHARTS); do \
		helm package $$chart -d .packages; \
	done
	@echo "✓ Charts packaged in .packages/"
	@ls -la .packages/

# ============================================================================
# Publishing
# ============================================================================

push-all: package
	@echo "=== Pushing to $(REGISTRY) ==="
	@for pkg in .packages/*.tgz; do \
		echo "Pushing $$pkg"; \
		helm push $$pkg oci://$(REGISTRY); \
	done
	@echo "✓ All charts pushed"

# ============================================================================
# Deployment
# ============================================================================

deploy-milvus:
	@echo "=== Deploying Milvus ==="
	helm upgrade --install milvus ./rag-milvus -n $(NAMESPACE) --create-namespace
	@echo "✓ Milvus deployed"

deploy-valkey:
	@echo "=== Deploying Valkey ==="
	helm upgrade --install valkey ./rag-valkey -n $(NAMESPACE) --create-namespace
	@echo "✓ Valkey deployed"

deploy-embeddings:
	@echo "=== Deploying Embeddings ==="
	helm upgrade --install embeddings ./rag-vllm-embeddings -n $(NAMESPACE) --create-namespace
	@echo "✓ Embeddings deployed"

deploy-docling:
	@echo "=== Deploying Docling ==="
	helm upgrade --install docling ./rag-docling -n $(NAMESPACE) --create-namespace
	@echo "✓ Docling deployed"

deploy-services:
	@echo "=== Deploying Services ==="
	helm upgrade --install services ./rag-services -n $(NAMESPACE) --create-namespace \
		--set namespace=$(NAMESPACE)
	@echo "✓ Services deployed"

deploy: deploy-milvus deploy-embeddings deploy-docling deploy-services
	@echo ""
	@echo "✓ All components deployed to $(NAMESPACE)"
	@echo ""
	@echo "Check status with:"
	@echo "  oc get pods -n $(NAMESPACE)"

# ============================================================================
# Undeployment
# ============================================================================

undeploy:
	@echo "=== Removing deployments from $(NAMESPACE) ==="
	-helm uninstall services -n $(NAMESPACE) 2>/dev/null
	-helm uninstall docling -n $(NAMESPACE) 2>/dev/null
	-helm uninstall embeddings -n $(NAMESPACE) 2>/dev/null
	-helm uninstall valkey -n $(NAMESPACE) 2>/dev/null
	-helm uninstall milvus -n $(NAMESPACE) 2>/dev/null
	@echo "✓ All deployments removed"

# ============================================================================
# Cleanup
# ============================================================================

clean:
	rm -rf .packages
	rm -rf rag-milvus/charts
	rm -f rag-milvus/Chart.lock
	@echo "✓ Build artifacts cleaned"
