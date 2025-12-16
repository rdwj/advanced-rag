# MCP Server for RAG Retrieval

The `retrieval-mcp/` directory contains a FastMCP-based MCP server that exposes RAG retrieval capabilities to agent applications like LibreChat.

For complete documentation, see [../retrieval-mcp/README.md](../retrieval-mcp/README.md).

## Quick Reference

### Available Tools

| Tool | Purpose |
|------|---------|
| `rag_search` | Semantic + keyword hybrid search over collections |
| `rag_search_filtered` | Search with metadata filters (file name, pattern, MIME type) |
| `rag_list_collections` | Discover available document collections |
| `rag_list_sources` | List documents within a collection |

### Running Locally

```bash
cd retrieval-mcp
make install          # Set up venv and install dependencies
make run-local        # Run with STDIO transport
make test             # Run pytest suite
```

### OpenShift Deployment

```bash
cd retrieval-mcp
make deploy PROJECT=advanced-rag
```

### Configuration

| Variable | Description |
|----------|-------------|
| `VECTOR_GATEWAY_URL` | URL of the vector-gateway service |
| `EMBEDDING_SERVICE_URL` | URL of the embedding service (optional) |
| `RERANK_SERVICE_URL` | URL of the rerank service (optional) |
