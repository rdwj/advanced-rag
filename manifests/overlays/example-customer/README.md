# Example Customer Overlay

This overlay demonstrates how to customize the advanced-rag deployment for a specific customer environment.

## Customizations

This example shows:
- Custom namespace (`customer-rag`)
- Self-hosted embedding model instead of OpenAI
- Self-hosted Caikit reranker instead of Cohere
- Local LLM for planning (Granite 3B)
- Pinned image versions for production stability

## Usage

1. Copy this directory to create a new customer overlay:
   ```bash
   cp -r overlays/example-customer overlays/acme-corp
   ```

2. Edit `kustomization.yaml` to customize:
   - `namespace`: Customer's OpenShift namespace
   - `patches`: Model endpoints, configurations
   - `images`: Specific version tags

3. Create secrets in the customer's namespace:
   ```bash
   oc create secret generic embedding-service-secrets \
     --from-literal=OPENAI_API_KEY="..." \
     -n customer-rag
   # ... repeat for other services
   ```

4. Deploy:
   ```bash
   oc apply -k overlays/acme-corp -n customer-rag
   ```

## Required Secrets

Each service needs its secrets created manually:
- `embedding-service-secrets`: OPENAI_API_KEY (or model-specific key)
- `plan-service-secrets`: OPENAI_API_KEY (or model-specific key)
- `evaluator-service-secrets`: OPENAI_API_KEY (or model-specific key)
- `rerank-service-secrets`: COHERE_API_KEY, RERANK_API_KEY
- `vector-gateway-secrets`: OPENAI_API_KEY

## Prerequisites

- Milvus deployed in customer namespace
- Model endpoints accessible (if using self-hosted)
- OpenShift namespace created with appropriate quotas
