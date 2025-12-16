# Databases

Vector databases and supporting infrastructure for RAG applications. Each directory contains configurations for local development and OpenShift deployment.

## Available Databases

| Database | Description | Best For |
|----------|-------------|----------|
| [pgvector](pgvector/) | PostgreSQL with vector extension | General purpose, hybrid search with SQL |
| [milvus](milvus/) | Dedicated vector database | Large-scale similarity search |
| [meilisearch](meilisearch/) | Search engine with vector support | Full-text + semantic search |
| [redis](redis/) | In-memory data store | Caching, session management |

## Quick Comparison

- **pgvector**: Best if you already use PostgreSQL or need ACID compliance
- **Milvus**: Best for large vector datasets (millions+) with high query throughput
- **Meilisearch**: Best for applications needing typo-tolerant keyword search alongside vectors
- **Redis**: Not a vector DB; use for caching embeddings or search results

## Structure

Each database directory follows a consistent layout:
- `local/` - Scripts and configs for local development with Podman
- `openshift/` - Kubernetes manifests for OpenShift deployment
