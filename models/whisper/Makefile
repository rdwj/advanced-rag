# Whisper Speech-to-Text Model Deployment
#
# Usage:
#   make help              - Show available targets
#   make deploy            - Deploy Whisper model
#   make status            - Check deployment status
#   make test              - Test transcription endpoint
#   make undeploy          - Remove the deployment
#
# Prerequisites:
#   - Logged into OpenShift cluster (oc login)
#   - GPU nodes available in cluster
#   - RHAIIS registry access configured

NAMESPACE ?= models
INFERENCE_SERVICE := whisper-large-fp8

.PHONY: help
help:
	@echo "Whisper Speech-to-Text Model Deployment"
	@echo ""
	@echo "DEPLOYMENT TARGETS:"
	@echo "  make deploy           Deploy Whisper model"
	@echo "  make undeploy         Remove the deployment"
	@echo ""
	@echo "STATUS & TESTING:"
	@echo "  make status           Show deployment status"
	@echo "  make logs             Show pod logs"
	@echo "  make test             Test model endpoint (list models)"
	@echo "  make test-transcribe  Test audio transcription"
	@echo ""
	@echo "OPTIONS:"
	@echo "  NAMESPACE=<ns>        Override namespace (default: models)"

# =============================================================================
# DEPLOYMENT
# =============================================================================

.PHONY: deploy
deploy:
	@./deploy.sh $(NAMESPACE)

.PHONY: undeploy
undeploy:
	@echo "Removing Whisper deployment..."
	@oc delete inferenceservice $(INFERENCE_SERVICE) -n $(NAMESPACE) --ignore-not-found
	@oc delete servingruntime vllm-rhaiis-whisper -n $(NAMESPACE) --ignore-not-found
	@echo "Deployment removed."

# =============================================================================
# STATUS & LOGS
# =============================================================================

.PHONY: status
status:
	@echo "=== Whisper Model Status in $(NAMESPACE) ==="
	@echo ""
	@echo "ServingRuntime:"
	@oc get servingruntime vllm-rhaiis-whisper -n $(NAMESPACE) 2>/dev/null || echo "  Not found"
	@echo ""
	@echo "InferenceService:"
	@oc get inferenceservice $(INFERENCE_SERVICE) -n $(NAMESPACE) 2>/dev/null || echo "  Not found"
	@echo ""
	@echo "Pods:"
	@oc get pods -l serving.kserve.io/inferenceservice=$(INFERENCE_SERVICE) -n $(NAMESPACE) 2>/dev/null || echo "  No pods found"
	@echo ""
	@echo "Route:"
	@oc get route $(INFERENCE_SERVICE) -n $(NAMESPACE) 2>/dev/null || echo "  No route found"

.PHONY: logs
logs:
	@oc logs -l serving.kserve.io/inferenceservice=$(INFERENCE_SERVICE) -n $(NAMESPACE) -c kserve-container --tail=100

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test:
	@echo "Testing Whisper endpoint..."
	@ROUTE_HOST=$$(oc get route $(INFERENCE_SERVICE) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "" && \
	echo "Available models:" && \
	curl -sk "$$ENDPOINT/v1/models" | python3 -c "import sys,json; r=json.load(sys.stdin); print(json.dumps(r, indent=2))"

.PHONY: test-transcribe
test-transcribe:
	@echo "Testing Whisper transcription..."
	@echo "NOTE: Provide an audio file with AUDIO_FILE=path/to/file.wav"
	@ROUTE_HOST=$$(oc get route $(INFERENCE_SERVICE) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	if [ -z "$(AUDIO_FILE)" ]; then \
		echo "ERROR: Set AUDIO_FILE=path/to/audio.wav"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "Audio file: $(AUDIO_FILE)" && \
	echo "" && \
	curl -sk "$$ENDPOINT/v1/audio/transcriptions" \
		-F file=@$(AUDIO_FILE) \
		-F model=$(INFERENCE_SERVICE) \
		-F response_format=json | python3 -c "import sys,json; r=json.load(sys.stdin); print('Transcription:', r.get('text', 'No text'))"
