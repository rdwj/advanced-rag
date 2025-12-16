# Faster-Whisper Service Makefile

IMAGE_REPO ?= quay.io/wjackson/faster-whisper
IMAGE_TAG ?= latest
NAMESPACE ?= faster-whisper

.PHONY: help build build-local push deploy undeploy logs test port-forward create-namespace

help:
	@echo "Faster-Whisper Service"
	@echo ""
	@echo "Targets:"
	@echo "  build            - Build container image (remote on ec2-dev for x86_64)"
	@echo "  build-local      - Build container image locally (Mac, may have arch issues)"
	@echo "  push             - Push image to registry"
	@echo "  deploy           - Deploy to OpenShift"
	@echo "  undeploy         - Remove from OpenShift"
	@echo "  logs             - Tail deployment logs"
	@echo "  test             - Run pytest"
	@echo "  port-forward     - Forward local port 8080 to service"
	@echo "  create-namespace - Create the OpenShift namespace"
	@echo ""
	@echo "Variables:"
	@echo "  IMAGE_REPO=$(IMAGE_REPO)"
	@echo "  IMAGE_TAG=$(IMAGE_TAG)"
	@echo "  NAMESPACE=$(NAMESPACE)"

# Build remotely on ec2-dev for x86_64 compatibility
build:
	@echo "Building on ec2-dev for x86_64 compatibility..."
	@echo "Use 'make build-local' for local builds (may have arch issues on Mac)"
	rsync -av --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
		./ ec2-dev:~/builds/faster-whisper/
	ssh ec2-dev 'cd ~/builds/faster-whisper && podman build -t $(IMAGE_REPO):$(IMAGE_TAG) -f Containerfile . --no-cache'

# Build locally (use with caution on Mac)
build-local:
	podman build --platform linux/amd64 -t $(IMAGE_REPO):$(IMAGE_TAG) -f Containerfile . --no-cache

# Push to registry (from ec2-dev after remote build)
push:
	ssh ec2-dev 'podman push $(IMAGE_REPO):$(IMAGE_TAG)'

# Push from local (after local build)
push-local:
	podman push $(IMAGE_REPO):$(IMAGE_TAG)

# Create namespace if it doesn't exist
create-namespace:
	@oc get namespace $(NAMESPACE) 2>/dev/null || oc new-project $(NAMESPACE)

# Deploy to OpenShift
deploy: create-namespace
	oc apply -k manifests/ -n $(NAMESPACE)
	@echo ""
	@echo "Waiting for deployment to be ready..."
	oc rollout status deployment/faster-whisper -n $(NAMESPACE) --timeout=300s

# Remove from OpenShift
undeploy:
	oc delete -k manifests/ -n $(NAMESPACE) --ignore-not-found

# Tail logs
logs:
	oc logs -f deployment/faster-whisper -n $(NAMESPACE)

# Run tests
test:
	pytest tests/ -v

# Port forward for local testing
port-forward:
	@echo "Forwarding localhost:8080 -> faster-whisper:8080"
	@echo "Test with: curl -X POST http://localhost:8080/transcribe -F 'file=@test.wav'"
	oc port-forward svc/faster-whisper 8080:8080 -n $(NAMESPACE)

# Check deployment status
status:
	@echo "=== Deployment ==="
	oc get deployment faster-whisper -n $(NAMESPACE)
	@echo ""
	@echo "=== Pods ==="
	oc get pods -l app=faster-whisper -n $(NAMESPACE)
	@echo ""
	@echo "=== Service ==="
	oc get svc faster-whisper -n $(NAMESPACE)
