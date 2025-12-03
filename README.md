# Advanced RAG with Adaptive Semantic Chunking

A production-ready Retrieval-Augmented Generation (RAG) pipeline that uses LLM-driven chunking plans for optimal document segmentation.

## Key Features

- **Adaptive Chunking**: LLM-generated chunking plans tailored to each document's structure
- **Hybrid Search**: Dense vectors + BM25 sparse search with RRF fusion
- **Multiple Vector Stores**: Milvus, PGVector, or Meilisearch backends
- **Microservices Architecture**: Independently deployable services for chunking, embedding, reranking, and retrieval
- **MCP Server**: FastMCP-based server for agent integration (LibreChat, Claude, etc.)
- **Iterative Evaluation**: Automatic plan refinement based on retrieval quality

## Architecture

```
Document → Extraction → LLM Planning → Chunking → Embedding → Vector Store
                                                                    ↓
                          Answer ← Rerank ← Hybrid Search ← Query
                            ↓
                        Evaluation → Plan Refinement (iterate)
```

## Project Structure

```
advanced-rag/
├── services/                     # Deployable microservices
│   ├── chunker_service/          # Go HTTP service for chunking
│   ├── plan_service/             # LLM chunking plan generator
│   ├── embedding_service/        # Batch embedding service
│   ├── rerank_service/           # Reranking abstraction
│   ├── evaluator_service/        # QA evaluation/scoring
│   ├── vector_gateway/           # Vector store abstraction
│   ├── rag_core/                 # Shared Python library
│   └── Makefile                  # Build/deploy automation
├── pipelines/                    # Python orchestration
│   ├── rag_pipeline/             # Core pipeline modules
│   ├── scripts/                  # Utility scripts (ingest, QA, etc.)
│   ├── tests/                    # pytest tests
│   └── kubeflow_ingest/          # Kubeflow pipeline definitions
├── retrieval-mcp/                # FastMCP server for RAG retrieval
├── databases/                    # Vector store configurations
│   ├── milvus/                   # Milvus setup (local + OpenShift)
│   ├── pgvector/                 # PostgreSQL + pgvector
│   └── meilisearch/              # Meilisearch configuration
├── docling-serve/                # Docling document conversion service
├── models/                       # Model configurations
├── agents/                       # Agent system prompts
├── docs/                         # Documentation
└── archived/                     # Deprecated content (preserved)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Go 1.21+
- Podman (for containers)
- OpenAI API key (or compatible endpoint)

### Setup

```bash
# Clone and set up environment
git clone <repository-url>
cd advanced-rag

# Create Python virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build the Go chunker
cd services/chunker_service
go build -o ../../bin/chunker ./cmd/chunker
cd ../..

# Configure
export OPENAI_API_KEY="your-api-key"
export VECTOR_BACKEND=milvus
export MILVUS_HOST=localhost
```

### Run

```bash
# Ingest documents
python pipelines/scripts/run_ingest_pipeline.py documents/*.pdf

# Query with the MCP server
cd retrieval-mcp && make run-local
```

## Documentation

- [Getting Started](docs/getting-started.md) - Setup and first steps
- [Architecture](docs/architecture.md) - System design and data flow
- [Microservices](docs/microservices.md) - Service deployment guide
- [Vector Stores](docs/vector-stores.md) - Backend configuration
- [MCP Server](docs/mcp-server.md) - Agent integration

## Microservices

| Service | Language | Purpose |
|---------|----------|---------|
| `chunker-service` | Go | Sliding-window text chunking |
| `plan-service` | Python | LLM-generated chunking plans |
| `embedding-service` | Python | Batch embeddings |
| `rerank-service` | Python | Result reranking |
| `evaluator-service` | Python | QA scoring and feedback |
| `vector-gateway` | Python | Unified vector store API |

### Deployment with Makefile

```bash
cd services

# Build all services remotely on ec2-dev
make build-all

# Push to OpenShift registry
make push-all

# Deploy all services
make deploy-all

# Check health
make status
```

## Vector Store Support

- **Milvus** (default): Native hybrid search with BM25
- **PGVector**: PostgreSQL with dense vectors + FTS
- **Meilisearch**: Experimental vector search

## MCP Server Tools

The retrieval-mcp server exposes:

- `rag_search` - Semantic + keyword hybrid search
- `rag_search_filtered` - Search with metadata filters
- `rag_list_collections` - Discover collections
- `rag_list_sources` - List documents in a collection

## OpenShift Deployment

```bash
# Deploy services using Makefile
cd services && make deploy-all

# Or deploy individual services
oc apply -f services/vector_gateway/manifests/ -n advanced-rag

# Deploy MCP server
cd retrieval-mcp && make deploy PROJECT=advanced-rag
```

## Development

### Testing

```bash
# Run pipeline tests
PYTHONPATH="pipelines:services" pytest pipelines/tests/

# Run MCP server tests
cd retrieval-mcp && make test
```

### Building Containers

```bash
cd services

# Self-contained service (chunker, plan, evaluator)
cd chunker_service
podman build --platform linux/amd64 -t chunker-service:latest -f Containerfile .

# Services requiring rag_core (embedding, rerank, vector-gateway)
# Build from services/ directory
podman build --platform linux/amd64 -t embedding-service:latest -f embedding_service/Containerfile .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
