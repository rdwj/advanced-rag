# Ingestion MCP Server

MCP server for document ingestion into the Advanced RAG pipeline. Provides tools for AI agents to ingest documents, URLs, and raw text into the vector database.

## Tools

| Tool | Description |
|------|-------------|
| `ingest_document` | Ingest a local file (PDF, DOCX, TXT, MD, HTML) |
| `ingest_from_url` | Fetch and ingest content from a URL |
| `ingest_text` | Ingest raw text directly |
| `get_collections` | List collections or get stats for a specific collection |

## Prerequisites

This MCP server requires the following services from the Advanced RAG pipeline:

- **Docling service** - Document parsing (PDF, DOCX)
- **Chunker service** - Text chunking
- **Vector gateway** - Embedding and storage (Milvus)

## Deployment

### Deploy to OpenShift

```bash
# Deploy to advanced-rag namespace
make deploy PROJECT=advanced-rag

# Verify
oc get pods -n advanced-rag -l app=ingestion-mcp
```

### Environment Variables

Configure these in `openshift.yaml` or via ConfigMap:

| Variable | Required | Description |
|----------|----------|-------------|
| `DOCLING_SERVICE_URL` | Yes | URL to docling-serve (e.g., `http://docling-serve:8080`) |
| `CHUNKER_SERVICE_URL` | Yes | URL to chunker service (e.g., `http://chunker-service:8080`) |
| `VECTOR_GATEWAY_URL` | Yes | URL to vector gateway (e.g., `http://vector-gateway:8080`) |
| `DEFAULT_COLLECTION` | No | Default Milvus collection (default: `rag_gateway`) |
| `AUTH_TOKEN` | No | Bearer token for service authentication |

## Agent Integration

Add to your LibreChat agent's MCP configuration:

```json
{
  "mcpServers": {
    "ingestion": {
      "url": "https://ingestion-mcp-advanced-rag.apps.your-cluster.com/mcp/"
    }
  }
}
```

## Local Development

```bash
# Install dependencies
make install

# Set environment variables
export DOCLING_SERVICE_URL="http://localhost:8081"
export CHUNKER_SERVICE_URL="http://localhost:8082"
export VECTOR_GATEWAY_URL="http://localhost:8083"

# Run locally
make run-local

# Test with cmcp
cmcp ".venv/bin/python -m src.main" tools/list
```

## Usage Examples

### Ingest a document

```
Use ingest_document to ingest /data/report.pdf into the "reports" collection
```

### Ingest from URL

```
Ingest the PDF at https://example.com/manual.pdf with tags ["manuals", "2024"]
```

### Ingest raw text

```
Ingest this meeting summary into the "meetings" collection: [text content]
```

## Chunking Strategies

| Strategy | Token Window | Overlap | Use Case |
|----------|--------------|---------|----------|
| `default` | 200 | 40 | General documents |
| `dense` | 100 | 30 | Short documents, high precision |
| `sparse` | 400 | 60 | Long documents, efficiency |

## Supported File Types

- PDF (`.pdf`)
- Word (`.docx`, `.doc`)
- Text (`.txt`)
- Markdown (`.md`)
- HTML (`.html`, `.htm`)