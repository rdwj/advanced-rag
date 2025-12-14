# PGVector on OpenShift

Deploy PostgreSQL with the pgvector extension on OpenShift for vector similarity search.

## Quick Deploy

```bash
# Set your namespace
NAMESPACE=pgvector  # Change to your desired namespace

# Create namespace
oc create namespace $NAMESPACE

# Deploy all resources
oc apply -k databases/pgvector/openshift -n $NAMESPACE

# Wait for pod to be ready
oc wait --for=condition=Ready pod -l app=pgvector -n $NAMESPACE --timeout=120s
```

## Verify Deployment

```bash
# Check pod status
oc get pods -l app=pgvector -n $NAMESPACE

# Check logs
oc logs -l app=pgvector -n $NAMESPACE --tail=50

# Verify pgvector extension is installed
oc exec -it deploy/pgvector -n $NAMESPACE -- psql -U postgres -d vector -c '\dx'
```

## Connection Details

| Setting | Value |
|---------|-------|
| Host (internal) | `pgvector.<namespace>.svc.cluster.local` |
| Port | `5432` |
| Database | `vector` |
| User | `postgres` (from secret) |
| Password | See `pgvector-credentials` secret |

Replace `<namespace>` with your actual namespace. For same-namespace access, use `pgvector:5432`.

### Connection String

```bash
# Get connection string from secret
oc get secret pgvector-credentials -n $NAMESPACE -o jsonpath='{.data.PGVECTOR_CONN}' | base64 -d

# Or construct manually (replace <namespace> with your namespace)
postgresql://postgres:<password>@pgvector.<namespace>.svc.cluster.local:5432/vector

# For same-namespace access
postgresql://postgres:<password>@pgvector:5432/vector
```

### Environment Variables for Applications

```yaml
envFrom:
  - secretRef:
      name: pgvector-credentials
```

Or individually:

```yaml
env:
  - name: PGVECTOR_CONN
    valueFrom:
      secretKeyRef:
        name: pgvector-credentials
        key: PGVECTOR_CONN
```

## Port Forward for Local Access

```bash
# Forward to localhost:5432
oc port-forward svc/pgvector 5432:5432 -n $NAMESPACE &

# Connect with psql
PGPASSWORD=changeme-in-production psql -h localhost -U postgres -d vector

# Or use connection string
psql "postgresql://postgres:changeme-in-production@localhost:5432/vector"
```

## Create Tables for RAG

```sql
-- Connect to database
\c vector

-- Verify extension
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create documents table (1536 dims for OpenAI text-embedding-3-small)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_l2_ops);

-- Or IVFFlat index (faster build, slower query)
-- CREATE INDEX IF NOT EXISTS documents_embedding_idx
--     ON documents USING ivfflat (embedding vector_l2_ops)
--     WITH (lists = 100);
```

## Similarity Search Examples

```sql
-- Insert document with embedding
INSERT INTO documents (content, metadata, embedding)
VALUES (
    'Example document content',
    '{"source": "test.pdf", "page": 1}'::jsonb,
    '[0.1, 0.2, ...]'::vector  -- 1536 dimensions
);

-- L2 distance (Euclidean)
SELECT id, content, embedding <-> '[0.1, 0.2, ...]' AS distance
FROM documents
ORDER BY embedding <-> '[0.1, 0.2, ...]'
LIMIT 5;

-- Cosine distance
SELECT id, content, embedding <=> '[0.1, 0.2, ...]' AS distance
FROM documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;

-- Inner product (negative, for maximization)
SELECT id, content, (embedding <#> '[0.1, 0.2, ...]') * -1 AS similarity
FROM documents
ORDER BY embedding <#> '[0.1, 0.2, ...]'
LIMIT 5;
```

## Production Considerations

### Change Default Credentials

```bash
# Edit the secret before deploying
# Or update after deployment (replace <namespace> with your namespace):
oc create secret generic pgvector-credentials \
  --from-literal=POSTGRES_USER=raguser \
  --from-literal=POSTGRES_PASSWORD='<strong-password>' \
  --from-literal=POSTGRES_DB=ragvector \
  --from-literal=PGVECTOR_CONN='postgresql://raguser:<strong-password>@pgvector:5432/ragvector' \
  --dry-run=client -o yaml | oc apply -n $NAMESPACE -f -

# Restart deployment to pick up new credentials
oc rollout restart deployment/pgvector -n $NAMESPACE
```

### Increase Storage

Edit `pvc.yaml` before deploying, or resize after:

```bash
# Resize PVC (if storage class supports it)
oc patch pvc pgvector-data -n $NAMESPACE -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
```

### Resource Limits

Edit `deployment.yaml` to adjust CPU/memory based on workload:

```yaml
resources:
  requests:
    cpu: "500m"
    memory: 1Gi
  limits:
    cpu: "4"
    memory: 8Gi
```

### Backup

```bash
# Create backup
oc exec deploy/pgvector -n $NAMESPACE -- pg_dump -U postgres vector > backup.sql

# Restore
oc exec -i deploy/pgvector -n $NAMESPACE -- psql -U postgres vector < backup.sql
```

## Cleanup

```bash
# Delete deployment (keeps PVC)
oc delete -k databases/pgvector/openshift -n $NAMESPACE

# Delete PVC to remove all data
oc delete pvc pgvector-data -n $NAMESPACE

# Delete namespace entirely
oc delete namespace $NAMESPACE
```

## Troubleshooting

### Pod fails to start

Check events:
```bash
oc describe pod -l app=pgvector -n $NAMESPACE
```

### Permission denied errors

The pgvector image runs as a non-root user. If you see permission errors, ensure the PVC has correct permissions:

```bash
# Check pod security context
oc get pod -l app=pgvector -n $NAMESPACE -o yaml | grep -A 20 securityContext
```

### Extension not loading

Verify the init script ran:
```bash
oc logs -l app=pgvector -n $NAMESPACE | grep -i vector
```

If needed, manually enable:
```bash
oc exec -it deploy/pgvector -n $NAMESPACE -- psql -U postgres -d vector -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```
