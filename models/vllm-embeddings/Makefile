# vLLM Embeddings - Testing Caikit-to-vLLM Migration
# Namespace: vllm-embeddings

NAMESPACE ?= vllm-embeddings
CLUSTER_DOMAIN := $(shell oc get ingresses.config/cluster -o jsonpath='{.spec.domain}' 2>/dev/null || echo "apps.cluster.local")

# URLs (set after deployment)
MINILM_URL = https://minilm-embedding-$(NAMESPACE).$(CLUSTER_DOMAIN)
GRANITE_URL = https://granite-embedding-$(NAMESPACE).$(CLUSTER_DOMAIN)
RERANKER_URL = https://msmarco-reranker-$(NAMESPACE).$(CLUSTER_DOMAIN)
BGE_RERANKER_URL = https://bge-reranker-$(NAMESPACE).$(CLUSTER_DOMAIN)

.PHONY: help setup deploy-minilm deploy-granite deploy-reranker deploy-bge deploy-all \
        undeploy-minilm undeploy-granite undeploy-reranker undeploy-bge undeploy-all \
        test-minilm test-granite test-reranker test-bge test-all \
        status logs-minilm logs-granite logs-reranker clean

help:
	@echo "vLLM Embeddings - Testing Plan"
	@echo ""
	@echo "Setup:"
	@echo "  make setup           - Create namespace and PVC"
	@echo ""
	@echo "Raw Deployments (for dev/testing):"
	@echo "  make deploy-minilm   - Deploy all-MiniLM-L6-v2 embedding model"
	@echo "  make deploy-granite  - Deploy Granite 278M embedding model"
	@echo "  make deploy-reranker - Deploy MS-MARCO reranker"
	@echo "  make deploy-bge      - Deploy BGE reranker"
	@echo "  make deploy-all      - Deploy all models (requires 4 GPUs)"
	@echo ""
	@echo "Test:"
	@echo "  make test-minilm     - Test MiniLM embeddings"
	@echo "  make test-granite    - Test Granite embeddings"
	@echo "  make test-reranker   - Test MS-MARCO reranker"
	@echo "  make test-bge        - Test BGE reranker"
	@echo "  make test-all        - Run all tests"
	@echo ""
	@echo "Cleanup:"
	@echo "  make undeploy-minilm - Remove MiniLM deployment"
	@echo "  make undeploy-all    - Remove all deployments"
	@echo "  make clean           - Remove namespace entirely"
	@echo ""
	@echo "Monitoring:"
	@echo "  make status          - Check deployment status"
	@echo "  make logs-minilm     - View MiniLM logs"
	@echo ""
	@echo "RHOAI Integration (Production):"
	@echo "  make deploy-rhoai-templates   - Deploy ServingRuntime templates to RHOAI"
	@echo "  make undeploy-rhoai-templates - Remove templates from RHOAI"
	@echo "  make status-kserve            - Check KServe resources"
	@echo ""
	@echo "See docs/RHOAI_DEPLOYMENT.md for full RHOAI deployment guide"
	@echo ""
	@echo "Cluster: $(CLUSTER_DOMAIN)"
	@echo "Namespace: $(NAMESPACE)"

# Setup
setup:
	@echo "=== Creating namespace and PVC ==="
	oc apply -f manifests/base/namespace.yaml
	oc apply -f manifests/base/model-cache-pvc.yaml -n $(NAMESPACE)
	@echo "Setup complete. PVC created for model caching."

# Deploy individual models (raw K8s deployments for dev/testing)
deploy-minilm: setup
	@echo "=== Deploying MiniLM Embedding Model ==="
	oc apply -f manifests/raw-deployments/minilm-embedding/ -n $(NAMESPACE)
	@echo "Waiting for deployment to start..."
	oc rollout status deployment/minilm-embedding -n $(NAMESPACE) --timeout=300s || true
	@echo ""
	@echo "MiniLM URL: $(MINILM_URL)"
	@echo "Test with: make test-minilm"

deploy-granite: setup
	@echo "=== Deploying Granite Embedding Model ==="
	oc apply -f manifests/raw-deployments/granite-embedding/ -n $(NAMESPACE)
	@echo "Waiting for deployment to start..."
	oc rollout status deployment/granite-embedding -n $(NAMESPACE) --timeout=300s || true
	@echo ""
	@echo "Granite URL: $(GRANITE_URL)"
	@echo "Test with: make test-granite"

deploy-reranker: setup
	@echo "=== Deploying MS-MARCO Reranker ==="
	oc apply -f manifests/raw-deployments/msmarco-reranker/ -n $(NAMESPACE)
	@echo "Waiting for deployment to start..."
	oc rollout status deployment/msmarco-reranker -n $(NAMESPACE) --timeout=300s || true
	@echo ""
	@echo "Reranker URL: $(RERANKER_URL)"
	@echo "Test with: make test-reranker"

deploy-bge: setup
	@echo "=== Deploying BGE Reranker ==="
	oc apply -f manifests/raw-deployments/bge-reranker/ -n $(NAMESPACE)
	@echo "Waiting for deployment to start..."
	oc rollout status deployment/bge-reranker -n $(NAMESPACE) --timeout=300s || true
	@echo ""
	@echo "BGE Reranker URL: $(BGE_RERANKER_URL)"
	@echo "Test with: make test-bge"

deploy-all: setup
	@echo "=== Deploying ALL models (requires 4 GPUs) ==="
	$(MAKE) deploy-minilm
	$(MAKE) deploy-granite
	$(MAKE) deploy-reranker
	$(MAKE) deploy-bge

# Undeploy
undeploy-minilm:
	@echo "=== Removing MiniLM deployment ==="
	oc delete -f manifests/raw-deployments/minilm-embedding/ -n $(NAMESPACE) --ignore-not-found

undeploy-granite:
	@echo "=== Removing Granite deployment ==="
	oc delete -f manifests/raw-deployments/granite-embedding/ -n $(NAMESPACE) --ignore-not-found

undeploy-reranker:
	@echo "=== Removing MS-MARCO reranker ==="
	oc delete -f manifests/raw-deployments/msmarco-reranker/ -n $(NAMESPACE) --ignore-not-found

undeploy-bge:
	@echo "=== Removing BGE reranker ==="
	oc delete -f manifests/raw-deployments/bge-reranker/ -n $(NAMESPACE) --ignore-not-found

undeploy-all:
	$(MAKE) undeploy-minilm
	$(MAKE) undeploy-granite
	$(MAKE) undeploy-reranker
	$(MAKE) undeploy-bge

clean:
	@echo "=== Removing entire namespace ==="
	oc delete namespace $(NAMESPACE) --ignore-not-found
	@echo "Cleaned up."

# Testing
test-minilm:
	@echo "=== Testing MiniLM Embedding Model ==="
	@echo "URL: $(MINILM_URL)"
	@echo ""
	@echo "1. Health check:"
	@curl -sk $(MINILM_URL)/health | jq . || echo "Health check failed"
	@echo ""
	@echo "2. Available models:"
	@curl -sk $(MINILM_URL)/v1/models | jq . || echo "Models endpoint failed"
	@echo ""
	@echo "3. Embedding test:"
	@curl -sk $(MINILM_URL)/v1/embeddings \
		-H "Content-Type: application/json" \
		-d '{"input": "Hello, world!", "model": "sentence-transformers/all-MiniLM-L6-v2"}' | jq '.data[0].embedding | length' || echo "Embedding failed"
	@echo ""
	@echo "Expected dimension: 384"

test-granite:
	@echo "=== Testing Granite Embedding Model ==="
	@echo "URL: $(GRANITE_URL)"
	@echo ""
	@echo "1. Health check:"
	@curl -sk $(GRANITE_URL)/health | jq . || echo "Health check failed"
	@echo ""
	@echo "2. Available models:"
	@curl -sk $(GRANITE_URL)/v1/models | jq . || echo "Models endpoint failed"
	@echo ""
	@echo "3. Embedding test:"
	@curl -sk $(GRANITE_URL)/v1/embeddings \
		-H "Content-Type: application/json" \
		-d '{"input": "Hello, world!", "model": "ibm-granite/granite-embedding-278m-multilingual"}' | jq '.data[0].embedding | length' || echo "Embedding failed"
	@echo ""
	@echo "Expected dimension: 768"

test-reranker:
	@echo "=== Testing MS-MARCO Reranker ==="
	@echo "URL: $(RERANKER_URL)"
	@echo ""
	@echo "1. Health check:"
	@curl -sk $(RERANKER_URL)/health | jq . || echo "Health check failed"
	@echo ""
	@echo "2. Available models:"
	@curl -sk $(RERANKER_URL)/v1/models | jq . || echo "Models endpoint failed"
	@echo ""
	@echo "3. Score test (/v1/score endpoint):"
	@curl -sk $(RERANKER_URL)/v1/score \
		-H "Content-Type: application/json" \
		-d '{"model": "cross-encoder/ms-marco-MiniLM-L12-v2", "text_1": "What is machine learning?", "text_2": "Machine learning is a branch of AI."}' | jq . || echo "Score endpoint failed"

test-bge:
	@echo "=== Testing BGE Reranker ==="
	@echo "URL: $(BGE_RERANKER_URL)"
	@echo ""
	@echo "1. Health check:"
	@curl -sk $(BGE_RERANKER_URL)/health | jq . || echo "Health check failed"
	@echo ""
	@echo "2. Available models:"
	@curl -sk $(BGE_RERANKER_URL)/v1/models | jq . || echo "Models endpoint failed"
	@echo ""
	@echo "3. Score test (/v1/score endpoint):"
	@curl -sk $(BGE_RERANKER_URL)/v1/score \
		-H "Content-Type: application/json" \
		-d '{"model": "BAAI/bge-reranker-v2-m3", "text_1": "What is machine learning?", "text_2": "Machine learning is a branch of AI."}' | jq . || echo "Score endpoint failed"

test-all:
	@echo "=========================================="
	@echo "Running all tests"
	@echo "=========================================="
	$(MAKE) test-minilm
	@echo ""
	$(MAKE) test-granite
	@echo ""
	$(MAKE) test-reranker
	@echo ""
	$(MAKE) test-bge

# Monitoring
status:
	@echo "=== Deployment Status ==="
	@oc get pods -n $(NAMESPACE) -o wide 2>/dev/null || echo "Namespace not found"
	@echo ""
	@echo "=== Routes ==="
	@oc get routes -n $(NAMESPACE) 2>/dev/null || echo "No routes found"
	@echo ""
	@echo "=== GPU Usage ==="
	@oc get pods -n $(NAMESPACE) -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].resources.requests.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null || echo "No GPU pods"

logs-minilm:
	@oc logs -f deployment/minilm-embedding -n $(NAMESPACE)

logs-granite:
	@oc logs -f deployment/granite-embedding -n $(NAMESPACE)

logs-reranker:
	@oc logs -f deployment/msmarco-reranker -n $(NAMESPACE)

logs-bge:
	@oc logs -f deployment/bge-reranker -n $(NAMESPACE)

# =============================================================================
# KServe Integration (OpenShift AI Model Deployments)
# =============================================================================
# These targets deploy models using KServe InferenceService, which integrates
# with OpenShift AI's Model Deployments dashboard.

.PHONY: deploy-rhoai-templates undeploy-rhoai-templates status-kserve

# RHOAI namespace for templates
RHOAI_NAMESPACE ?= redhat-ods-applications

# Deploy ServingRuntime Templates to RHOAI (makes them selectable in OpenShift AI dashboard)
deploy-rhoai-templates:
	@echo "=== Deploying vLLM ServingRuntime Templates to RHOAI ==="
	@echo "Namespace: $(RHOAI_NAMESPACE)"
	oc apply -f manifests/rhoai/templates/ -n $(RHOAI_NAMESPACE)
	@echo ""
	@echo "Templates deployed. Check OpenShift AI → Settings → Serving Runtimes"
	@echo "You should see: vLLM Embedding Runtime, vLLM Reranker Runtime"
	@echo ""
	oc get templates -n $(RHOAI_NAMESPACE) | grep -E "^NAME|vllm"

undeploy-rhoai-templates:
	@echo "=== Removing vLLM ServingRuntime Templates from RHOAI ==="
	oc delete template vllm-embedding-runtime -n $(RHOAI_NAMESPACE) --ignore-not-found
	oc delete template vllm-reranker-runtime -n $(RHOAI_NAMESPACE) --ignore-not-found

# Status for KServe resources
status-kserve:
	@echo "=== ServingRuntimes ==="
	@oc get servingruntime -n $(NAMESPACE) 2>/dev/null || echo "No ServingRuntimes found"
	@echo ""
	@echo "=== InferenceServices ==="
	@oc get inferenceservice -n $(NAMESPACE) 2>/dev/null || echo "No InferenceServices found"
	@echo ""
	@echo "=== Routes (manually created for RawDeployment) ==="
	@oc get routes -n $(NAMESPACE) 2>/dev/null || echo "No routes found"
