# Advanced RAG Helm Charts

This directory contains Helm charts for deploying a complete Advanced RAG (Retrieval-Augmented Generation) infrastructure on Red Hat OpenShift.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RAG Infrastructure                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   rag-milvus    │  │   rag-valkey    │  │   rag-docling   │             │
│  │ (Vector Store)  │  │    (Cache)      │  │ (Doc Convert)   │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                     │                      │
│           └────────────────────┼─────────────────────┘                      │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────┐             │
│  │                    rag-vllm-embeddings                     │             │
│  │     (Embedding & Reranking Models - GPU Required)          │             │
│  └─────────────────────────────┬─────────────────────────────┘             │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────┐             │
│  │                      rag-services                          │             │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │             │
│  │  │ chunker │ │  plan   │ │embedding│ │ rerank  │          │             │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │             │
│  │  ┌─────────┐ ┌─────────────────────────────────┐          │             │
│  │  │evaluator│ │       vector-gateway            │          │             │
│  │  └─────────┘ └─────────────────────────────────┘          │             │
│  └───────────────────────────────────────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Charts

| Chart | Description | GPU Required |
|-------|-------------|--------------|
| `rag-milvus` | Milvus vector database (wrapper around official chart) | No |
| `rag-valkey` | Valkey cache (Redis-compatible, BSD-3 licensed) | No |
| `rag-vllm-embeddings` | vLLM-based embedding and reranking models | Yes |
| `rag-docling` | Document conversion service (PDF, DOCX, etc.) | Optional |
| `rag-services` | RAG microservices bundle (6 services) | No |

## Deployment Order

Deploy charts in this order due to dependencies:

1. **Phase 1 - Foundation**
   - `rag-milvus` - Vector database
   - `rag-valkey` - Caching (optional)

2. **Phase 2 - Models**
   - `rag-vllm-embeddings` - Embedding and reranker models (requires GPU node)

3. **Phase 3 - Document Processing**
   - `rag-docling` - Document conversion

4. **Phase 4 - Services**
   - `rag-services` - RAG microservices (depends on all above)

## Quick Start

### Prerequisites

1. OpenShift cluster with GPU nodes (for rag-vllm-embeddings)
2. Helm 3.x installed
3. `oc` CLI authenticated to your cluster

### Deploy Minimal Stack

```bash
# Create namespace
oc new-project advanced-rag

# Phase 1: Deploy Milvus
helm install milvus ./rag-milvus -n advanced-rag

# Phase 2: Deploy embedding models (requires GPU node)
helm install embeddings ./rag-vllm-embeddings -n advanced-rag \
  --set embeddings.minilm.enabled=true \
  --set rerankers.msmarco.enabled=true

# Phase 3: Deploy Docling
helm install docling ./rag-docling -n advanced-rag

# Phase 4: Create secrets and deploy services
oc create secret generic rag-api-keys \
  --from-literal=OPENAI_API_KEY="sk-..." \
  -n advanced-rag

helm install services ./rag-services -n advanced-rag \
  --set namespace=advanced-rag
```

### Using ArgoCD

See the `argocd/` directory for App-of-Apps deployment patterns.

## Configuration

Each chart has extensive documentation in its `values.yaml` file. Common configurations:

### GPU Scheduling

Charts that require GPU use tolerations:

```yaml
gpu:
  tolerations:
    - key: nvidia.com/gpu
      operator: Exists
      effect: NoSchedule
```

### OpenShift Routes

All charts support OpenShift Routes:

```yaml
openshift:
  route:
    enabled: true
    tls:
      termination: edge
```

### Image Registries

For air-gapped environments, override image sources:

```yaml
image:
  repository: your-registry.example.com/path/image
  tag: "v1.0.0"
```

## Environment Profiles

Example values files for different environments are provided in `examples/`:

- `examples/values-minimal.yaml` - Bare minimum for testing
- `examples/values-development.yaml` - Development settings
- `examples/values-production.yaml` - Production-ready settings
- `examples/values-airgapped.yaml` - Air-gapped environment

## Connectivity Profiles

### Fully Connected
Default configuration - pulls images from public registries.

### Minimally Connected
Override image registries to use a proxy or mirror.

### Air-Gapped
1. Pre-pull all images to internal registry
2. Use `values-airgapped.yaml` as a template
3. Ensure all chart dependencies are available locally

## Versioning

Charts follow [Semantic Versioning](https://semver.org/):
- **Major**: Breaking changes to values.yaml or behavior
- **Minor**: New features, backward compatible
- **Patch**: Bug fixes, backward compatible

## Contributing

1. Make changes to chart templates
2. Update `Chart.yaml` version
3. Run `helm lint` on all charts
4. Test deployment on a development cluster
5. Submit PR

## Support

For issues and questions, open a GitHub issue or contact the team.
