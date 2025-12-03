# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a multi-component advanced RAG (Retrieval-Augmented Generation) pipeline. The system uses an LLM to suggest chunking parameters for each document, then deterministically chunks using a Go binary, embeds, and stores in vector databases.

## Project Structure

```
advanced-rag/
├── services/                     # FastAPI + Go microservices (deployable)
│   ├── chunker_service/          # Go HTTP service (self-contained)
│   ├── embedding_service/        # FastAPI embedding wrapper
│   ├── plan_service/             # LLM chunking plan generator
│   ├── rerank_service/           # Reranking abstraction
│   ├── evaluator_service/        # QA evaluation/scoring
│   ├── vector_gateway/           # Milvus/PGVector/memory abstraction
│   ├── rag_core/                 # Shared Python library (embedding, rerank, config)
│   └── Makefile                  # Build/deploy automation
├── pipelines/                    # Pipeline orchestration
│   ├── rag_pipeline/             # Python orchestration modules
│   ├── scripts/                  # Utility scripts (ingest, QA, comparison)
│   ├── tests/                    # pytest tests
│   ├── kubeflow_ingest/          # KubeFlow pipeline definitions
│   ├── qa_manifest.json          # QA test manifests
│   └── qa_labels.jsonl           # QA test labels
├── retrieval-mcp/                # FastMCP-based MCP server for RAG retrieval
├── databases/                    # Vector store configurations
│   ├── milvus/                   # Milvus setup (local/ and openshift/)
│   ├── pgvector/                 # PostgreSQL + pgvector (local/)
│   └── meilisearch/              # Meilisearch configuration (local/)
├── bin/                          # Compiled binaries (Go chunker CLI)
├── config/                       # Configuration files (rag-config.yaml)
├── test_files/                   # Test documents for development
├── agents/                       # Agent system prompts
├── docling-serve/                # OpenShift deployment for document conversion
├── models/                       # Model configurations
├── docs/                         # Consolidated documentation
└── archived/                     # Deprecated content (preserved for reference)
```

## Important Development Notes

### Testing and Deployment Integrity

**CRITICAL**: When testing or fixing issues, do NOT create workarounds or kludges. If something doesn't work:
1. Fix the actual deployment manifests, scripts, or configuration files
2. Ensure the fix is committed and will work for future deployments
3. Document any required environment variables or prerequisites

The goal is that service deployments work correctly out of the box.

### Container Standards

- Use `Containerfile`, NOT `Dockerfile`
- Use Podman, NOT Docker
- Always build with `--platform linux/amd64` for OpenShift compatibility
- Base images: Red Hat UBI (`registry.redhat.io/ubi9/*`)

## Build Commands

### Go Chunker (CLI + HTTP Service)
```bash
# CLI binary for local pipeline use
cd services/chunker_service
go build -o ../../bin/chunker ./cmd/chunker

# HTTP server for service deployment
go build -o chunker-server ./cmd/chunker-server
./chunker-server  # listens on :8080
```

### Python Environment
```bash
python -m venv .venv && source .venv/bin/activate
pip install openai tavily-python pymilvus psycopg[binary] pgvector meilisearch pytest requests
```

### Run Tests
```bash
PYTHONPATH="pipelines:services" pytest pipelines/tests/
PYTHONPATH="pipelines:services" pytest pipelines/tests/test_token_utils.py -v  # Single test file
```

### Build Microservices (Using Makefile - Recommended)
```bash
cd services

# Build all services remotely on ec2-dev
make build-all

# Build individual services
make build-embedding
make build-plan
make build-chunker

# Push to OpenShift registry
make push-all

# Deploy all services
make deploy-all

# Check health
make status
```

### Build Microservices (Local Podman)
```bash
cd services

# Self-contained services (chunker, plan, evaluator) - build from their directory
cd chunker_service
podman build --platform linux/amd64 -t chunker-service:latest -f Containerfile .

# Services requiring rag_core (embedding, rerank, vector-gateway) - build from services/
cd ..
podman build --platform linux/amd64 -t embedding-service:latest -f embedding_service/Containerfile .
podman build --platform linux/amd64 -t rerank-service:latest -f rerank_service/Containerfile .
podman build --platform linux/amd64 -t vector-gateway:latest -f vector_gateway/Containerfile .
```

### retrieval-mcp (FastMCP Server)
```bash
cd retrieval-mcp
make install          # Set up venv and install dependencies
make run-local        # Run with STDIO transport (local development)
make test             # Run pytest suite
make deploy           # Deploy to OpenShift

# Test with cmcp
cmcp ".venv/bin/python -m src.main" tools/list

# Generate new components
fips-agents generate tool my_tool --description "Tool description" --async
fips-agents generate resource my_resource --description "Resource description"
fips-agents generate prompt my_prompt --description "Prompt description"
```

## Key Environment Variables

### Required
- `OPENAI_API_KEY` - Primary API key for LLM operations

### Vector Store Selection
- `VECTOR_BACKEND` - `milvus` (default), `pgvector`, or `meilisearch`

### Milvus
- `MILVUS_HOST`, `MILVUS_PORT` or `MILVUS_URI`
- `MILVUS_COLLECTION`, `MILVUS_RRF_K`, `MILVUS_OVERFETCH`, `MILVUS_SKIP_DROP`

### PGVector
- `PGVECTOR_CONN` - PostgreSQL connection DSN
- `PGVECTOR_SCHEMA` - Optional schema name

### Meilisearch
- `MEILI_HOST`, `MEILI_API_KEY`, `MEILI_INDEX`
- `MEILI_SEMANTIC_RATIO`, `MEILI_RANKING_THRESHOLD`

### Embeddings/Rerank
- `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`
- `RERANK_PROVIDER` (`cohere`, `openai`, `none`), `RERANK_API_KEY`, `RERANK_MODEL`

### Microservice URLs
- `DOCLING_SERVICE_URL`, `CHUNKER_SERVICE_URL`, `PLAN_SERVICE_URL`
- `EMBEDDING_SERVICE_URL`, `RERANK_SERVICE_URL`, `EVALUATOR_SERVICE_URL`

## Architecture

### Pipeline Flow
1. **Extraction** - PDF→Markdown via Docling; fallback to pypdf
2. **Planning** - LLM suggests `ChunkingPlan` (window_size, overlap, mode, break_on_headings)
3. **Chunking** - Go CLI applies sliding-window chunking (chars/tokens/lines modes)
4. **Embedding** - OpenAI or compatible embedding API
5. **Storage** - Milvus (BM25 hybrid), PGVector (FTS+dense RRF), or Meilisearch
6. **Retrieval** - Hybrid search with RRF fusion
7. **Evaluation** - Optional iterative refinement with JSON scoring

### Python Module Layout

**`services/rag_core/`** - Shared library used by services:
- `config.py` - YAML-based configuration with provider support
- `embed.py` - Multi-provider embedding abstraction
- `rerank.py` - Multi-provider reranking
- `models.py` - Pydantic configuration models
- `token_utils.py` - Token counting utilities
- `providers/` - Provider implementations (OpenAI, Cohere, Caikit, Jina)

**`pipelines/rag_pipeline/`** - Orchestration modules:
- `extract.py` - Document extraction with Docling
- `plan.py` - LLM-driven chunking plan generation
- `chunk.py` - Python→Go chunker bridge
- `embed.py` - Re-exports from rag_core (backward compatibility)
- `milvus_io.py` - Milvus schema, insert, hybrid search
- `vector_store.py` - Backend-agnostic store abstraction
- `rerank.py` - Re-exports from rag_core
- `config.py` - Environment-based configuration

### Go Chunker (`services/chunker_service/`)
- `pkg/chunking/` - Core chunking logic, `ChunkingPlan` struct
- `cmd/chunker/` - CLI entry point (reads stdin, outputs JSON chunks)
- `cmd/chunker-server/` - HTTP server wrapping the CLI logic

### Microservices (`services/`)
All services expose `/healthz` and their primary endpoint. Python services use FastAPI with a `lib/` subdirectory containing business logic:

| Service | Language | Endpoint | Description |
|---------|----------|----------|-------------|
| `chunker_service` | Go | `POST /chunk` | Sliding-window text chunking |
| `plan_service` | Python | `POST /plan` | LLM-generated ChunkingPlan |
| `embedding_service` | Python | `POST /embed` | Batch embeddings (OpenAI/OSS) |
| `rerank_service` | Python | `POST /rerank` | Rerank provider abstraction |
| `evaluator_service` | Python | `POST /evaluate` | QA scoring with JSON feedback |
| `vector_gateway` | Python | `POST /search`, `POST /upsert` | Vector store abstraction |

Python service structure:
```
services/<name>/
├── app.py              # FastAPI entrypoint
├── lib/                # Business logic (config.py, <module>.py)
├── requirements.txt
├── Containerfile
└── manifests/          # OpenShift deployment YAML
```

## Common Tasks

### Ingest Documents
```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_ingest_pipeline.py test_files/*.pdf
```

### Run QA Manifest
```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_qa_manifest.py --manifest pipelines/qa_manifest_pg.json --output-dir qa_runs
```

### Test Chunking Plan on Single File
```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/test_plan_on_file.py test_files/sample.pdf
```

### Iterative Evaluation
```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/iterative_chunk_eval.py --question "..." --file test_files/doc.pdf
```

### Model Comparison (OpenAI vs OSS Plan Models)
```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_iterative_comparison.py \
  --profile diabetes_cpg --break-on-headings --top-k 8 --max-context-tokens 1400
```

### Direct Chunker CLI Usage
```bash
cat myfile.txt | bin/chunker \
  --plan-json '{"window_size":200,"overlap":40,"mode":"tokens"}' \
  --meta-json '{"file_name":"myfile.txt"}'
```

## OpenShift Deployment

### Using the Makefile (Recommended)
```bash
cd services

# Full deployment (build, push, deploy)
make all

# Or step by step
make build-all
make push-all
make deploy-all

# Restart without rebuilding
make rollout-all

# Check health
make status
```

### Manual Deployment
```bash
# Apply manifests (deployment, service, route)
oc apply -f services/vector_gateway/manifests/ -n advanced-rag

# Wait for rollout
oc wait --for=condition=Available deployment/vector-gateway -n advanced-rag --timeout=120s

# Verify
oc get route vector-gateway -n advanced-rag -o jsonpath='{.spec.host}'
```

### Service URLs (Internal)
Services communicate internally via `http://<service>.<namespace>.svc.cluster.local:<port>`:
```bash
export CHUNKER_SERVICE_URL=http://chunker-service.advanced-rag.svc.cluster.local:8080
export PLAN_SERVICE_URL=http://plan-service.advanced-rag.svc.cluster.local:8000
export EMBEDDING_SERVICE_URL=http://embedding-service.advanced-rag.svc.cluster.local:8000
export VECTOR_GATEWAY_URL=http://vector-gateway.advanced-rag.svc.cluster.local:8005
```

## Testing Notes

- Tests require `pipelines/` and `services/` on `PYTHONPATH` (handled by `conftest.py`)
- Mock network calls (OpenAI, Milvus) when adding tests
- Include edge cases: empty input, overlap extremes, mode variants

### Testing FastMCP Decorated Functions

FastMCP decorators (`@mcp.tool`, `@mcp.resource`, `@mcp.prompt`) wrap functions in special objects. Access the underlying function using `.fn`:

```python
from src.tools.my_tool import my_tool

my_tool_fn = my_tool.fn  # Access underlying function

@pytest.mark.asyncio
async def test_my_tool():
    result = await my_tool_fn(param1="value1")
    assert result == "expected"
```

## Service Fallback Pattern

Python pipeline modules check for `*_SERVICE_URL` environment variables. If set, they call the service; otherwise, they fall back to local execution:
- `CHUNKER_SERVICE_URL` → calls service, else runs `bin/chunker` CLI
- `PLAN_SERVICE_URL` → calls service, else uses local `plan.py`
- `EMBEDDING_SERVICE_URL` → calls service, else uses OpenAI directly

This allows running the pipeline both locally (for development) and in OpenShift (for production).

## Database Configuration

Vector store configurations are in `databases/`:

```
databases/
├── milvus/
│   ├── local/           # standalone_embed.sh, podman_milvus.sh
│   ├── openshift/       # Kubernetes manifests, operator config
│   └── README.md
├── pgvector/
│   ├── local/           # compose.yml, init scripts
│   └── README.md
└── meilisearch/
    ├── local/           # meili.sh startup script
    └── README.md
```

### Starting Local Vector Stores

```bash
# Milvus
cd databases/milvus/local && ./standalone_embed.sh start

# PGVector
cd databases/pgvector/local && podman-compose up -d

# Meilisearch
cd databases/meilisearch/local && ./meili.sh start
```

## Pipelines Directory

The `pipelines/` directory is designed to be movable to a separate repository for project-specific orchestration. It contains:

- `rag_pipeline/` - Python orchestration modules
- `scripts/` - CLI utilities for ingestion, QA, evaluation
- `tests/` - pytest test suite
- `kubeflow_ingest/` - KubeFlow pipeline definitions for OpenShift AI
- QA manifests and labels

When moved to a separate repo, pipelines should call deployed services via HTTP rather than importing local modules.

## Archived Content

The `archived/` directory contains deprecated content preserved for reference:

- `experiment_results/` - Historical experiment JSON outputs
- `qa_runs/` - Previous QA evaluation runs
- `docling_test_results/` - Docling conversion test outputs
- `planning_docs/` - Original planning and design documents

These files are NOT deleted, just moved out of the main project tree for cleaner organization.
