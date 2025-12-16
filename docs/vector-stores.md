# Vector Store Configuration

This project supports multiple vector store backends for storing and searching embeddings.

For database deployment instructions, see the README files in `databases/milvus/`, `databases/pgvector/`, and `databases/meilisearch/`.

## Backend Selection

Set the `VECTOR_BACKEND` environment variable:

```bash
export VECTOR_BACKEND=milvus      # Default, recommended
export VECTOR_BACKEND=pgvector    # PostgreSQL + pgvector
export VECTOR_BACKEND=meilisearch # Meilisearch (experimental vectors)
```

## Milvus (Recommended)

Native hybrid search with BM25 sparse vectors and dense embeddings.

### Configuration

```bash
# Connection
export MILVUS_HOST=localhost
export MILVUS_PORT=19530
# Or use URI:
export MILVUS_URI=http://milvus.example.com:19530

# Collection settings
export MILVUS_COLLECTION=rag_chunks
export MILVUS_RRF_K=60
export MILVUS_OVERFETCH=3
export MILVUS_SKIP_DROP=false
```

### Local Development

```bash
cd databases/milvus/local
./standalone_embed.sh start
```

## PGVector

PostgreSQL with the pgvector extension, using full-text search (FTS) combined with dense vectors.

### Configuration

```bash
export PGVECTOR_CONN="postgresql://user:password@localhost:5432/ragdb"
export PGVECTOR_SCHEMA=public  # Optional
```

### Local Development

```bash
cd databases/pgvector/local
podman-compose up -d
```

The init script enables the pgvector extension automatically.

## Meilisearch

Meilisearch with experimental vector search support (v1.14+).

### Configuration

```bash
export MEILI_HOST=http://localhost:7700
export MEILI_API_KEY=your-api-key
export MEILI_INDEX=rag_documents

# Hybrid search settings
export MEILI_SEMANTIC_RATIO=0.5
export MEILI_RANKING_THRESHOLD=0.0

# Optional embedder settings
export MEILI_EMBEDDER=default
export MEILI_MANAGED_EMBEDDER=false
export MEILI_EMBEDDER_MODEL=text-embedding-3-small
```

### Local Development

```bash
cd databases/meilisearch/local
./meili.sh start
```

## Ingestion

The ingestion pipeline automatically creates collections/tables/indexes for the chosen backend:

```bash
PYTHONPATH="pipelines:services" python pipelines/scripts/run_ingest_pipeline.py test_files/*.pdf
```

## Schema

All backends store similar data:

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | string | Unique identifier (clipped to 64 chars) |
| `file_name` | string | Source document name |
| `file_path` | string | Full path to source |
| `chunk_index` | int | Position in document |
| `text` | string | Chunk text content |
| `embedding` | vector | Dense embedding |
| `mime_type` | string | Document MIME type |
| `page` | int | Page number (if available) |
| `heading` | string | Section heading (if available) |

## Performance Comparison

| Backend | Best For | Hybrid Search | Notes |
|---------|----------|---------------|-------|
| **Milvus** | Large-scale deployments | Native BM25 + dense | More infrastructure required |
| **PGVector** | Smaller datasets | FTS + dense (manual RRF) | Leverages PostgreSQL expertise |
| **Meilisearch** | Search-focused apps | Score-based ratio | Vector search is experimental |
