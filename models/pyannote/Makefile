# Pyannote Speaker Diarization Server Deployment
#
# Usage:
#   make help              - Show available targets
#   make deploy            - Deploy pyannote server
#   make status            - Check deployment status
#   make test              - Test health endpoint
#   make undeploy          - Remove the deployment
#
# Prerequisites:
#   - Logged into OpenShift cluster (oc login)
#   - GPU nodes available in cluster
#   - HF_TOKEN environment variable set

# =============================================================================
# CONFIGURATION
# =============================================================================

NAMESPACE ?= models
REGISTRY ?= quay.io/wjackson
IMAGE_NAME ?= pyannote
IMAGE_TAG ?= latest
IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
PULL_SECRET ?= pyannote-pull-secret
DEPLOYMENT_NAME := pyannote-server

# Build configuration
EC2_DEV_HOST ?= ec2-dev
EC2_DEV_BUILD_DIR ?= ~/builds/pyannote-server

.PHONY: help
help:
	@echo "Pyannote Speaker Diarization Server Deployment"
	@echo ""
	@echo "DEPLOYMENT TARGETS:"
	@echo "  make deploy           Deploy pyannote server"
	@echo "  make undeploy         Remove the deployment"
	@echo "  make create-secret    Create HuggingFace token secret (requires HF_TOKEN)"
	@echo ""
	@echo "BUILD TARGETS:"
	@echo "  make build            Build container on ec2-dev"
	@echo "  make push             Push image to registry"
	@echo "  make build-push       Build and push in one step"
	@echo ""
	@echo "STATUS & TESTING:"
	@echo "  make status           Show deployment status"
	@echo "  make logs             Show pod logs"
	@echo "  make test             Test health endpoint"
	@echo "  make test-diarize     Test diarization (requires AUDIO_FILE)"
	@echo ""
	@echo "OPTIONS:"
	@echo "  NAMESPACE=<ns>        Override namespace (default: models)"
	@echo "  REGISTRY=<reg>        Override registry (default: quay.io/wjackson)"
	@echo "  IMAGE_TAG=<tag>       Override image tag (default: latest)"
	@echo "  HF_TOKEN=<token>      HuggingFace API token (for create-secret)"
	@echo "  AUDIO_FILE=<path>     Audio file for test-diarize"

# =============================================================================
# BUILD TARGETS
# =============================================================================

.PHONY: build
build:
	@echo "Building pyannote container on $(EC2_DEV_HOST)..."
	@rsync -avz --delete \
		--exclude='.git' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='.venv' \
		./ $(EC2_DEV_HOST):$(EC2_DEV_BUILD_DIR)/
	@ssh $(EC2_DEV_HOST) 'cd $(EC2_DEV_BUILD_DIR) && podman build --no-cache -t $(IMAGE) -f Containerfile .'
	@echo "Build complete: $(IMAGE)"

.PHONY: push
push:
	@echo "Pushing $(IMAGE) to registry..."
	@ssh $(EC2_DEV_HOST) 'podman push $(IMAGE)'
	@echo "Push complete."

.PHONY: build-push
build-push: build push
	@echo "Build and push complete: $(IMAGE)"

# =============================================================================
# DEPLOYMENT TARGETS
# =============================================================================

.PHONY: deploy
deploy:
	@./deploy.sh $(NAMESPACE) $(IMAGE) $(PULL_SECRET)

.PHONY: undeploy
undeploy:
	@echo "Removing pyannote deployment from $(NAMESPACE)..."
	@oc delete deployment $(DEPLOYMENT_NAME) -n $(NAMESPACE) --ignore-not-found
	@oc delete service $(DEPLOYMENT_NAME) -n $(NAMESPACE) --ignore-not-found
	@oc delete route $(DEPLOYMENT_NAME) -n $(NAMESPACE) --ignore-not-found
	@echo "Deployment removed."
	@echo "Note: Secrets and PVC were preserved. Remove manually if needed:"
	@echo "  oc delete secret pyannote-hf-token -n $(NAMESPACE)"
	@echo "  oc delete pvc pyannote-models -n $(NAMESPACE)"

.PHONY: create-secret
create-secret:
	@if [ -z "$(HF_TOKEN)" ]; then \
		echo "ERROR: HF_TOKEN environment variable is required"; \
		echo "Usage: HF_TOKEN=hf_xxx make create-secret"; \
		exit 1; \
	fi
	@echo "Creating HuggingFace token secret in $(NAMESPACE)..."
	@oc get namespace $(NAMESPACE) >/dev/null 2>&1 || oc new-project $(NAMESPACE)
	@oc create secret generic pyannote-hf-token \
		--from-literal=token=$(HF_TOKEN) \
		-n $(NAMESPACE) \
		--dry-run=client -o yaml | oc apply -f -
	@echo "Secret created/updated."

# =============================================================================
# STATUS & LOGS
# =============================================================================

.PHONY: status
status:
	@echo "=== Pyannote Server Status in $(NAMESPACE) ==="
	@echo ""
	@echo "Deployment:"
	@oc get deployment $(DEPLOYMENT_NAME) -n $(NAMESPACE) 2>/dev/null || echo "  Not found"
	@echo ""
	@echo "Pods:"
	@oc get pods -l app=$(DEPLOYMENT_NAME) -n $(NAMESPACE) 2>/dev/null || echo "  No pods found"
	@echo ""
	@echo "Service:"
	@oc get service $(DEPLOYMENT_NAME) -n $(NAMESPACE) 2>/dev/null || echo "  Not found"
	@echo ""
	@echo "Route:"
	@oc get route $(DEPLOYMENT_NAME) -n $(NAMESPACE) 2>/dev/null || echo "  No route found"
	@echo ""
	@echo "Secrets:"
	@oc get secret pyannote-hf-token -n $(NAMESPACE) 2>/dev/null && echo "  pyannote-hf-token: exists" || echo "  pyannote-hf-token: NOT FOUND (required)"

.PHONY: logs
logs:
	@oc logs -l app=$(DEPLOYMENT_NAME) -n $(NAMESPACE) --tail=100

.PHONY: logs-follow
logs-follow:
	@oc logs -l app=$(DEPLOYMENT_NAME) -n $(NAMESPACE) -f

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test:
	@echo "Testing pyannote health endpoint..."
	@ROUTE_HOST=$$(oc get route $(DEPLOYMENT_NAME) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "" && \
	echo "Health check:" && \
	curl -sk "$$ENDPOINT/health" | python3 -c "import sys,json; r=json.load(sys.stdin); print(json.dumps(r, indent=2))"

.PHONY: test-diarize
test-diarize:
	@echo "Testing pyannote diarization..."
	@ROUTE_HOST=$$(oc get route $(DEPLOYMENT_NAME) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	if [ -z "$(AUDIO_FILE)" ]; then \
		echo "ERROR: Set AUDIO_FILE=path/to/audio.wav"; \
		echo "Note: File must be WAV format. Convert with:"; \
		echo "  ffmpeg -i input.m4a -ar 16000 -ac 1 output.wav"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "Audio file: $(AUDIO_FILE)" && \
	echo "" && \
	echo "Running diarization (this may take a while for long audio)..." && \
	curl -sk "$$ENDPOINT/v1/diarize" \
		-F "file=@$(AUDIO_FILE)" | python3 -c "import sys,json; r=json.load(sys.stdin); segments=r.get('segments',[]); print(f'Detected {r.get(\"num_speakers\", 0)} speakers in {len(segments)} segments'); print(); [print(f\"{s['speaker']}: {s['start']:.2f}s - {s['end']:.2f}s\") for s in segments[:10]]; print('...' if len(segments) > 10 else '')"

.PHONY: get-endpoint
get-endpoint:
	@ROUTE_HOST=$$(oc get route $(DEPLOYMENT_NAME) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "Route not found"; \
		exit 1; \
	fi && \
	echo "https://$$ROUTE_HOST"
