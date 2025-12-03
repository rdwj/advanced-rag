# MCP Server for RAG Retrieval

The `retrieval-mcp/` directory contains a FastMCP-based MCP server that exposes RAG retrieval capabilities to agent applications like LibreChat.

## Overview

The MCP server provides tools for:

- **Semantic search** over document collections
- **Filtered search** with metadata constraints
- **Collection discovery** and source listing
- **Citation-formatted results** ready for LLM output

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  LibreChat /    │     │   MCP Server     │     │  Vector Gateway │
│  Agent App      │────▶│   (FastMCP)      │────▶│  (enhanced)     │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                         │
                             ┌────────────────┬──────────┴──────────┐
                             ▼                ▼                     ▼
                       ┌──────────┐    ┌────────────┐    ┌──────────────┐
                       │  Milvus  │    │  Rerank    │    │  Embedding   │
                       │ (hybrid) │    │  Service   │    │   Service    │
                       └──────────┘    └────────────┘    └──────────────┘
```

## Available Tools

### `rag_search`

Search over document collections using semantic + keyword hybrid search.

**Parameters:**

- `query` (required): Natural language search query
- `collection` (required): Collection name to search
- `top_k` (optional): Number of results (1-20, default 5)
- `response_format` (optional): `"concise"` or `"detailed"`
- `min_score` (optional): Minimum relevance threshold

### `rag_search_filtered`

Search with metadata filters to narrow results.

**Additional Parameters:**

- `file_name`: Filter by exact file name
- `file_pattern`: Filter by pattern (e.g., "DMC-BRAKE*")
- `mime_type`: Filter by document type

### `rag_list_collections`

Discover available document collections.

### `rag_list_sources`

List documents within a specific collection.

## Backend Behavior (Automatic)

These features are always applied:

- **Hybrid Search**: Dense vector + BM25 with RRF fusion
- **Reranking**: Results reranked before returning
- **Context Expansion**: Surrounding chunks from same document
- **Citation Formatting**: Pre-formatted for LLM output

## Running Locally

```bash
cd retrieval-mcp
make install          # Set up venv and install dependencies
make run-local        # Run with STDIO transport
make test             # Run pytest suite
```

## OpenShift Deployment

```bash
cd retrieval-mcp
make deploy PROJECT=advanced-rag
```

## Configuration

Environment variables:

- `VECTOR_GATEWAY_URL` - URL of the vector-gateway service
- `EMBEDDING_SERVICE_URL` - URL of the embedding service (optional)
- `RERANK_SERVICE_URL` - URL of the rerank service (optional)

## Testing

```bash
# Test with cmcp
cmcp ".venv/bin/python -m src.main" tools/list

# Run pytest
cd retrieval-mcp && make test
```

## Generating New Components

Use fips-agents to generate new tools, resources, or prompts:

```bash
cd retrieval-mcp
fips-agents generate tool my_tool --description "Tool description" --async
fips-agents generate resource my_resource --description "Resource description"
fips-agents generate prompt my_prompt --description "Prompt description"
```

For detailed tool definitions and implementation notes, see the source code in `retrieval-mcp/src/tools/`.
