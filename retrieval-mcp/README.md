# Retrieval MCP Server

A FastMCP server that exposes RAG (Retrieval-Augmented Generation) capabilities via the Model Context Protocol. This server provides AI agents with tools to search document collections, list available content, and optimize queries for better retrieval.

## Features

- **Hybrid Search**: Dense vector + BM25 sparse search with reranking
- **Context Expansion**: Automatically include surrounding chunks for better context
- **Query Rewriting**: LLM-powered query optimization for improved retrieval
- **Collection Discovery**: Tools to explore available collections and documents
- **Flexible Filtering**: Filter by file name, glob pattern, or MIME type
- **Multiple Output Formats**: Concise citations or detailed JSON responses

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Agent      │────▶│  retrieval-mcp  │────▶│ vector-gateway  │
│   (Claude,      │ MCP │  (FastMCP)      │HTTP │ (FastAPI)       │
│   LibreChat)    │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Milvus/PGVector│
                                                │  (Vector Store) │
                                                └─────────────────┘
```

## MCP Tools

### `rag_search`

Primary retrieval tool. Performs hybrid search with reranking and context expansion.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Natural language search query |
| `collection` | string | required | Collection to search |
| `top_k` | int | 5 | Number of results (1-20) |
| `context_window` | int | 2 | Surrounding chunks to include (0-5) |
| `file_name` | string | null | Filter by exact file name |
| `file_pattern` | string | null | Filter by glob pattern (e.g., `DMC-BRAKE*`) |
| `mime_type` | string | null | Filter by MIME type |
| `min_score` | float | 0.0 | Minimum relevance threshold (0.0-1.0) |
| `response_format` | string | "concise" | `concise` or `detailed` |

### `rag_list_collections`

Discover available document collections in the vector store.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `response_format` | string | "concise" | `concise` (names) or `detailed` (with stats) |

### `rag_list_sources`

List documents within a specific collection.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `collection` | string | required | Collection name |
| `response_format` | string | "concise" | `concise` or `detailed` |
| `limit` | int | 50 | Maximum sources to return (1-500) |

### `rag_rewrite_query`

Optimize a query for better retrieval using LLM sampling.

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Original query to rewrite |
| `domain_context` | string | null | Domain hints (e.g., "technical maintenance manuals") |
| `rewrite_style` | string | "expand" | `expand`, `simplify`, or `technical` |

## Quick Start

### Local Development

```bash
# Install dependencies
make install

# Run with STDIO transport
make run-local

# Test with cmcp
cmcp ".venv/bin/python -m src.main" tools/list
```

### Deploy to OpenShift

```bash
# Deploy to advanced-rag namespace
make deploy PROJECT=advanced-rag

# Check status
oc get pods -n advanced-rag -l app=retrieval-mcp
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VECTOR_GATEWAY_URL` | `http://vector-gateway.advanced-rag.svc.cluster.local:8000` | Vector gateway service URL |
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` (local) or `http` (OpenShift) |
| `MCP_HTTP_PORT` | `8080` | HTTP server port (when using http transport) |
| `MCP_HTTP_PATH` | `/mcp/` | HTTP endpoint path |

## Project Structure

```
retrieval-mcp/
├── src/
│   ├── core/           # MCP server initialization
│   ├── lib/            # Shared utilities (vector client, formatters)
│   ├── tools/          # MCP tool implementations
│   │   ├── rag_search.py
│   │   ├── rag_list_collections.py
│   │   ├── rag_list_sources.py
│   │   └── rag_rewrite_query.py
│   ├── prompts/        # MCP prompts (if any)
│   ├── resources/      # MCP resources (if any)
│   └── middleware/     # Request middleware
├── tests/              # pytest test suite
├── docs/               # Documentation
├── Containerfile       # Container build
├── openshift.yaml      # OpenShift manifests
└── Makefile            # Build/deploy automation
```

## Integration Examples

### LibreChat Agent

Configure the MCP server in your agent's system prompt:

```
You have access to a document retrieval system via MCP tools.
Use the collection "clinical_guidelines" for all searches.

Available tools:
- rag_search: Search for relevant content
- rag_list_sources: See available documents
- rag_rewrite_query: Optimize queries for technical content
```

### Claude Code

Add to your MCP server configuration:

```json
{
  "mcpServers": {
    "retrieval": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/retrieval-mcp",
      "env": {
        "VECTOR_GATEWAY_URL": "https://vector-gateway-advanced-rag.apps.your-cluster.com"
      }
    }
  }
}
```

## Testing

```bash
# Run unit tests
make test

# Run specific test file
pytest tests/tools/test_rag_search.py -v

# Test with MCP Inspector (after deployment)
npx @modelcontextprotocol/inspector https://<route-url>/mcp/
```

## Development

### Adding New Tools

1. Create a new file in `src/tools/`:

```python
from typing import Annotated
from pydantic import Field
from fastmcp.exceptions import ToolError
from core.app import mcp

@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
    }
)
async def my_new_tool(
    param: Annotated[str, Field(description="Parameter description")],
) -> str:
    """Tool description for the LLM."""
    # Implementation
    return "result"
```

2. The tool is automatically discovered and registered at startup.

### Using Generators

```bash
# Generate a new tool
fips-agents generate tool my_tool --description "Tool description" --async

# Generate with context support
fips-agents generate tool search_tool --description "Search tool" --async --with-context
```

## Requirements

- Python 3.11+
- FastMCP 2.11+
- Access to vector-gateway service (for production use)
- OpenShift CLI (`oc`) for deployment

## Related Components

- [vector-gateway](../services/vector_gateway/) - Vector store abstraction service
- [embedding-service](../services/embedding_service/) - Embedding generation
- [rerank-service](../services/rerank_service/) - Result reranking
