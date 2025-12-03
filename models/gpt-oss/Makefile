# GPT-OSS 20B Model Deployment
#
# Usage:
#   make help              - Show available targets
#   make deploy            - Deploy GPT-OSS 20B model
#   make status            - Check deployment status
#   make test              - Test the model endpoint
#   make undeploy          - Remove the deployment
#
# Prerequisites:
#   - Logged into OpenShift cluster (oc login)
#   - Model files uploaded to S3 (see scripts/stream_to_s3.py)
#   - GPU nodes available in cluster

NAMESPACE ?= gpt-oss
INFERENCE_SERVICE := gpt-oss-20b-rhaiis

.PHONY: help
help:
	@echo "GPT-OSS 20B Model Deployment"
	@echo ""
	@echo "DEPLOYMENT TARGETS:"
	@echo "  make deploy           Deploy GPT-OSS 20B model"
	@echo "  make undeploy         Remove the deployment"
	@echo ""
	@echo "STATUS & TESTING:"
	@echo "  make status           Show deployment status"
	@echo "  make logs             Show pod logs"
	@echo "  make test             Test the model endpoint"
	@echo "  make test-stream      Test streaming response"
	@echo ""
	@echo "MODEL UPLOAD (run from OpenShift AI Workbench):"
	@echo "  make upload           Upload model to S3 using stream_to_s3.py"
	@echo ""
	@echo "OPTIONS:"
	@echo "  NAMESPACE=<ns>        Override namespace (default: gpt-oss)"

# =============================================================================
# DEPLOYMENT
# =============================================================================

.PHONY: deploy
deploy:
	@./deploy.sh $(NAMESPACE)

.PHONY: undeploy
undeploy:
	@echo "Removing GPT-OSS 20B deployment..."
	@oc delete inferenceservice $(INFERENCE_SERVICE) -n $(NAMESPACE) --ignore-not-found
	@oc delete servingruntime vllm-gptoss-runtime -n $(NAMESPACE) --ignore-not-found
	@echo "Deployment removed. Data connection secret preserved."

# =============================================================================
# STATUS & LOGS
# =============================================================================

.PHONY: status
status:
	@echo "=== GPT-OSS 20B Status in $(NAMESPACE) ==="
	@echo ""
	@echo "ServingRuntime:"
	@oc get servingruntime vllm-gptoss-runtime -n $(NAMESPACE) 2>/dev/null || echo "  Not found"
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
	@oc logs -l serving.kserve.io/inferenceservice=$(INFERENCE_SERVICE) -n $(NAMESPACE) --tail=100

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test:
	@echo "Testing GPT-OSS 20B endpoint..."
	@ROUTE_HOST=$$(oc get route $(INFERENCE_SERVICE) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "" && \
	echo "Sending test request..." && \
	curl -sk -X POST "$$ENDPOINT/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-d '{"model": "$(INFERENCE_SERVICE)", "messages": [{"role": "user", "content": "Say hello in exactly 5 words."}], "max_tokens": 50}' | \
	python3 -c "import sys,json; r=json.load(sys.stdin); print('Response:', r['choices'][0]['message']['content'])"

.PHONY: test-stream
test-stream:
	@echo "Testing GPT-OSS 20B streaming endpoint..."
	@ROUTE_HOST=$$(oc get route $(INFERENCE_SERVICE) -n $(NAMESPACE) -o jsonpath='{.spec.host}' 2>/dev/null) && \
	if [ -z "$$ROUTE_HOST" ]; then \
		echo "ERROR: Route not found. Deploy with: make deploy"; \
		exit 1; \
	fi && \
	ENDPOINT="https://$$ROUTE_HOST" && \
	echo "Endpoint: $$ENDPOINT" && \
	echo "" && \
	echo "Streaming response:" && \
	curl -sk -X POST "$$ENDPOINT/v1/chat/completions" \
		-H "Content-Type: application/json" \
		-d '{"model": "$(INFERENCE_SERVICE)", "messages": [{"role": "user", "content": "Count from 1 to 5."}], "max_tokens": 50, "stream": true}'

# =============================================================================
# MODEL UPLOAD (run from OpenShift AI Workbench)
# =============================================================================

.PHONY: upload
upload:
	@echo "Uploading GPT-OSS 20B model to S3..."
	@echo "This should be run from an OpenShift AI Workbench with S3 access."
	@python scripts/stream_to_s3.py
