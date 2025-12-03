# PGVector (PostgreSQL + Vector Extension)

PostgreSQL with the pgvector extension for vector similarity search. Combines the reliability of PostgreSQL with efficient vector operations.

## Features

- Full PostgreSQL functionality with vector search
- Multiple index types (IVFFlat, HNSW)
- Native full-text search for hybrid retrieval
- ACID compliance and mature ecosystem

## Directory Structure

```
pgvector/
├── local/                  # Local development setup
│   ├── compose.yml         # Podman/Docker Compose file
│   ├── .env.example        # Environment template
│   ├── pgvector-agent.env  # Agent environment variables
│   └── initdb/             # Initialization scripts
│       └── 01_enable_pgvector.sql
└── openshift/              # OpenShift deployment
    ├── kustomization.yaml  # Kustomize configuration
    ├── deployment.yaml     # Deployment manifest
    ├── service.yaml        # Service definition
    ├── secret.yaml         # Credentials secret
    ├── configmap.yaml      # Configuration
    ├── pvc.yaml            # Persistent storage
    └── README.md           # Detailed deployment guide
```

## Local Development

### Quick Start

```bash
cd local

# Copy and customize environment (optional)
cp .env.example .env

# Start container
podman compose up -d

# Verify
podman ps --filter name=pgvector
podman exec -it pgvector psql -U postgres -d vector -c '\dx'
```

### Default Configuration

| Setting | Value |
|---------|-------|
| Host | localhost |
| Port | 5432 |
| Database | vector |
| User | postgres |
| Password | postgres |

### Connection

```bash
# Interactive psql
podman exec -it pgvector psql -U postgres -d vector

# One-liner query
podman exec -it pgvector psql -U postgres -d vector -c "SELECT COUNT(*) FROM documents;"
```

### Data Management

```bash
# Stop container (preserves data)
podman compose stop

# Remove container and volume (destroys data)
podman compose down -v
```

## OpenShift Deployment

See [openshift/README.md](openshift/README.md) for detailed instructions.

### Quick Deploy

```bash
# Deploy using Kustomize
oc apply -k openshift/ -n your-namespace

# Wait for pod
oc wait --for=condition=Ready pods -l app=pgvector -n your-namespace --timeout=120s

# Get service endpoint
oc get svc pgvector -n your-namespace
```

### Production Considerations

Before deploying to production, update the secret:

```bash
oc create secret generic pgvector-credentials \
  --from-literal=POSTGRES_USER=your-user \
  --from-literal=POSTGRES_PASSWORD=your-secure-password \
  --from-literal=POSTGRES_DB=your-database \
  -n your-namespace --dry-run=client -o yaml | oc apply -f -
```

## Usage Examples

### Create Table with Vector Column

```sql
-- Create table (1536 dimensions for OpenAI embeddings)
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding vector(1536)
);

-- Create HNSW index (recommended for most cases)
CREATE INDEX documents_embedding_idx ON documents
USING hnsw (embedding vector_cosine_ops);

-- Alternative: IVFFlat index (faster build, slower queries)
CREATE INDEX documents_embedding_ivf_idx ON documents
USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```

### Insert Data

```sql
INSERT INTO documents (content, metadata, embedding)
VALUES (
    'Document text content',
    '{"source": "file.pdf", "page": 1}'::jsonb,
    '[0.01, 0.02, ...]'::vector
);
```

### Vector Search

```sql
-- Cosine similarity (most common for embeddings)
SELECT id, content, 1 - (embedding <=> query_embedding) AS similarity
FROM documents
ORDER BY embedding <=> '[0.01, 0.02, ...]'::vector
LIMIT 10;

-- L2 distance
SELECT id, content, embedding <-> '[0.01, 0.02, ...]'::vector AS distance
FROM documents
ORDER BY embedding <-> '[0.01, 0.02, ...]'::vector
LIMIT 10;
```

### Hybrid Search (Vector + Full-Text)

```sql
-- Create FTS index
ALTER TABLE documents ADD COLUMN fts_vector tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX documents_fts_idx ON documents USING gin(fts_vector);

-- Hybrid query with RRF fusion
WITH vector_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS vector_rank
    FROM documents
    ORDER BY embedding <=> $1
    LIMIT 20
),
fts_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(fts_vector, query) DESC) AS fts_rank
    FROM documents, plainto_tsquery('english', $2) query
    WHERE fts_vector @@ query
    LIMIT 20
)
SELECT d.id, d.content,
       1.0 / (60 + COALESCE(v.vector_rank, 1000)) +
       1.0 / (60 + COALESCE(f.fts_rank, 1000)) AS rrf_score
FROM documents d
LEFT JOIN vector_results v ON d.id = v.id
LEFT JOIN fts_results f ON d.id = f.id
WHERE v.id IS NOT NULL OR f.id IS NOT NULL
ORDER BY rrf_score DESC
LIMIT 10;
```

### Python Connection

```python
import psycopg
from pgvector.psycopg import register_vector

# Connect
conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/vector")
register_vector(conn)

# Search
with conn.cursor() as cur:
    cur.execute("""
        SELECT id, content, 1 - (embedding <=> %s) AS similarity
        FROM documents
        ORDER BY embedding <=> %s
        LIMIT 10
    """, (query_embedding, query_embedding))
    results = cur.fetchall()
```

## Notes

- Image: `docker.io/pgvector/pgvector:pg17`
- pgvector extension is auto-enabled via `initdb/01_enable_pgvector.sql`
- HNSW index recommended for production (better query performance)
- For very large datasets, consider IVFFlat with appropriate `lists` parameter
