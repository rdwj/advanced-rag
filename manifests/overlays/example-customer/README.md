# Example Customer Overlay

Template for customizing the advanced-rag deployment for a specific customer environment. See the [parent README](../../README.md) for full deployment instructions and secrets configuration.

## What This Example Configures

- Custom namespace (`customer-rag`)
- Self-hosted embedding model instead of OpenAI
- Self-hosted Caikit reranker instead of Cohere
- Local LLM for planning (Granite 3B)
- Pinned image versions for production stability

## Usage

1. Copy this directory:
   ```bash
   cp -r overlays/example-customer overlays/acme-corp
   ```

2. Edit `kustomization.yaml`:
   - `namespace`: Customer's OpenShift namespace
   - `patches`: Model endpoints, configurations
   - `images`: Specific version tags

3. Create secrets (see parent README for full list)

4. Deploy:
   ```bash
   make deploy OVERLAY=acme-corp NAMESPACE=customer-rag
   ```

## Prerequisites

- Milvus deployed in customer namespace
- Model endpoints accessible (if using self-hosted)
- OpenShift namespace created with appropriate quotas
