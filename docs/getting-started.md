# Getting Started

This guide will help you set up and run the Advanced RAG pipeline.

## Prerequisites

- Python 3.11+
- Go 1.21+ (for building the chunker)
- Podman (for container builds)
- Access to OpenAI API (or compatible endpoint)
- Vector store: Milvus, PostgreSQL+pgvector, or Meilisearch

## Quick Start

### 1. Clone and Set Up Environment

```bash
git clone <repository-url>
cd advanced-rag

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Build the Go Chunker

```bash
cd services/chunker_service
go build -o ../../bin/chunker ./cmd/chunker
cd ../..
```

### 3. Configure Environment

```bash
# Required
export OPENAI_API_KEY="your-api-key"

# Vector store (choose one)
export VECTOR_BACKEND=milvus
export MILVUS_HOST=localhost
export MILVUS_PORT=19530

# Or for PGVector:
# export VECTOR_BACKEND=pgvector
# export PGVECTOR_CONN="postgresql://user:pass@localhost:5432/ragdb"
```

### 4. Start a Vector Store

#### Option A: Milvus (Local)

```bash
cd databases/milvus/local
./standalone_embed.sh start
```

#### Option B: PGVector (Podman Compose)

```bash
cd databases/pgvector/local
podman-compose up -d
```

### 5. Ingest Documents

```bash
# From repository root
PYTHONPATH="pipelines:services" python pipelines/scripts/run_ingest_pipeline.py test_files/sample.pdf
```

### 6. Run Queries

```bash
# Interactive QA
PYTHONPATH="pipelines:services" python pipelines/scripts/run_qa_manifest.py --manifest qa_manifest.json

# Or use the MCP server (for agent integration)
cd retrieval-mcp
make install
make run-local
```

## Project Structure

```
advanced-rag/
├── services/                     # Deployable microservices + rag_core
├── pipelines/                    # Python orchestration (rag_pipeline, scripts, tests)
├── retrieval-mcp/                # MCP server for agent integration
├── databases/                    # Vector store configurations
├── docling-serve/                # Document conversion service
├── models/                       # Model configurations
├── agents/                       # Agent system prompts
├── docs/                         # Documentation
└── archived/                     # Deprecated content
```

## Next Steps

- [Architecture Overview](architecture.md) - Understand the system design
- [Microservices Guide](microservices.md) - Deploy and scale services
- [Vector Stores](vector-stores.md) - Configure your preferred backend
- [MCP Server](mcp-server.md) - Integrate with agent applications

## Common Tasks

### Ingest a Directory of PDFs

```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_ingest_pipeline.py /path/to/pdfs/*.pdf
```

### Run Iterative Evaluation

```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/iterative_chunk_eval.py \
  --question "What is the recommended screening interval?" \
  --file test_files/guidelines.pdf
```

### Compare Plan Models

```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_iterative_comparison.py \
  --profile diabetes_cpg \
  --break-on-headings \
  --top-k 8
```

### Deploy to OpenShift

```bash
# Deploy all services via Makefile
cd services && make deploy-all

# Or deploy individual services
oc apply -f services/vector_gateway/manifests/ -n advanced-rag

# Deploy MCP server
cd retrieval-mcp && make deploy PROJECT=advanced-rag
```

## Troubleshooting

### Chunker Not Found

Build the Go binary:

```bash
cd services/chunker_service && go build -o ../../bin/chunker ./cmd/chunker
```

### Milvus Connection Failed

Check if Milvus is running:

```bash
curl http://localhost:19530/healthz
```

### Embedding Errors

Verify your API key and model settings:

```bash
export OPENAI_API_KEY="your-key"
export EMBEDDING_MODEL="text-embedding-3-small"
```

### Import Errors

Ensure PYTHONPATH includes both pipelines and services:

```bash
export PYTHONPATH="pipelines:services"
```
